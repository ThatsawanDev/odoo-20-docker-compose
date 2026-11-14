# Part of Odoo. See LICENSE file for full copyright and licensing details.

import hashlib
import hmac
import logging
import time
import requests
import json
from datetime import datetime, timedelta
from pprint import pformat

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tools import LazyTranslate
from odoo.tools.urls import urljoin

from odoo.addons.smart_sale_tiktok import const

_lt = LazyTranslate(__name__)
_logger = logging.getLogger(__name__)


class TikTokRateLimitError(Exception):
    """Raised when the TikTok Shop API rate limit is reached."""
    def __init__(self, operation):
        self.operation = operation
        super().__init__()


class TikTokApiError(Exception):
    """Raised when the TikTok Shop API returns an error."""
    def __init__(self, shop, operation, request_id, error_code, error_message):
        super().__init__(
            shop.env._(
                "In TikTok Shop '%(shop_name)s', an error %(error_code)s occurred during the "
                "API operation '%(operation)s' with request ID '%(request_id)s':\n%(error_message)s",
                shop_name=shop.name,
                operation=operation,
                request_id=request_id,
                error_code=error_code,
                error_message=error_message,
            )
        )


def get_api_sign(account, path, params, body=''):
    """Generate HMAC-SHA256 signature for authenticated TikTok Shop Open API requests.
    
    Signing string rules: app_key + sorted query params (key+val) + body + app_secret
    """
    account.ensure_one()
    sorted_params = sorted(params.items())
    param_string = ''.join(
        f'{key}{val}' for key, val in sorted_params
        if key not in ('sign', 'access_token')
    )
    signing_string = f"{path}{param_string}{body}"
    return hmac.new(
        account.app_secret.encode('utf-8'),
        signing_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()


def request_access_token(shop, authorization_code=None, is_refresh=False):
    """Request or refresh access token from TikTok Shop Open API."""
    shop.ensure_one()
    account = shop.account_id
    params = {'app_key': account.app_key, 'app_secret': account.app_secret}

    if is_refresh:
        params['refresh_token'] = shop.refresh_token
        params['grant_type'] = 'refresh_token'
        operation = 'refresh_token'
    elif authorization_code or shop.env.context.get('authorization_code'):
        code = authorization_code or shop.env.context.get('authorization_code')
        params['auth_code'] = code
        params['grant_type'] = 'authorized_code'
        operation = 'get_token'
    else:
        raise UserError(shop.env._("Authorization Code is required to request an Access Token."))

    path = const.API_OPERATIONS_MAPPING[operation]['url_path']
    resp = requests.get(
        urljoin('https://auth.tiktok-shops.com', path),
        params=params,
        timeout=15,
    )
    if resp.status_code == 429:
        raise TikTokRateLimitError(operation)
    if resp.status_code != 200:
        raise ValidationError(shop.env._("Error connecting to TikTok API: %s", resp.text))

    res_json = resp.json()
    if res_json.get('code', 0) != 0:
        raise UserError(shop.env._("TikTok API returned error [%(code)s]: %(msg)s", 
                                   code=res_json.get('code'), msg=res_json.get('message')))

    data = res_json.get('data', {})
    access_expiration = data.get('access_token_expire_in')
    refresh_expiration = data.get('refresh_token_expire_in')
    now = fields.Datetime.now()
    # TikTok returns Unix expiry timestamps. Retain compatibility with sandbox
    # responses that return a duration.
    def expiration_datetime(value, fallback_seconds):
        value = int(value or fallback_seconds)
        if value > 1_000_000_000:
            return fields.Datetime.to_datetime(datetime.utcfromtimestamp(value))
        return now + timedelta(seconds=value)

    shop.write({
        'access_token': data.get('access_token'),
        'refresh_token': data.get('refresh_token'),
        'access_token_expiration_date': expiration_datetime(access_expiration, 604800),
        'refresh_token_expiration_date': expiration_datetime(
            refresh_expiration, 2592000,
        ),
        'shop_identifier': data.get('open_id', shop.shop_identifier),
    })
    return data


def make_tiktok_api_request(
    shop, operation, params=None, body=None, method=None, path_values=None,
):
    """Send an authenticated API request to TikTok Shop Open API."""
    shop.ensure_one()
    account = shop.account_id
    api_type = const.API_OPERATIONS_MAPPING[operation]['api_type']
    params = params or {}
    operation_data = const.API_OPERATIONS_MAPPING[operation]
    method = method or operation_data.get('method', 'GET')
    body_str = (
        json.dumps(body, ensure_ascii=False, separators=(',', ':'))
        if body is not None else ''
    )

    if api_type != 'public':
        if not shop.access_token or not shop.access_token_expiration_date:
            request_access_token(shop)
        elif shop.access_token_expiration_date < fields.Datetime.now() + timedelta(minutes=5):
            request_access_token(shop, is_refresh=True)
    endpoint = const.API_ENDPOINTS.get(account.region, const.API_ENDPOINTS['GLOBAL'])
    path = operation_data['url_path'].format(**(path_values or {}))
    timestamp = int(time.time())

    params.update({
        'app_key': account.app_key,
        'timestamp': str(timestamp),
        'shop_cipher': shop.shop_cipher or '',
    })
    params['sign'] = get_api_sign(account, path, params, body_str)

    url = urljoin(endpoint, path)
    _logger.info("TikTok API request - Operation: %s\nParams: %s", operation, params)

    headers = {'content-type': 'application/json'}
    if api_type != 'public':
        headers['x-tts-access-token'] = shop.access_token
    resp = requests.request(
        method,
        url,
        params=params,
        data=body_str if body is not None else None,
        headers=headers,
        timeout=30,
    )
    if resp.status_code == 429:
        raise TikTokRateLimitError(operation)
    if resp.status_code != 200:
        raise TikTokApiError(shop, operation, 'N/A', resp.status_code, resp.text)

    response_content = resp.json()
    if response_content.get('code', 0) != 0:
        if str(response_content.get('code')) in ['429', '1000003']:
            raise TikTokRateLimitError(operation)
        raise TikTokApiError(shop, operation, response_content.get('request_id', 'N/A'),
                             response_content.get('code'), response_content.get('message', 'Unknown Error'))

    return response_content.get('data', response_content)


def verify_webhook_signature(account, raw_body, signature):
    """Validate TikTok's Authorization header against the exact request body."""
    if not signature:
        return False
    message = account.app_key.encode() + raw_body
    expected = hmac.new(
        account.app_secret.encode(), message, hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected.lower(), signature.strip().lower())
