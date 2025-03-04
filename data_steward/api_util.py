"""Utilities used by the API definition, and authentication/authorization/roles."""

import datetime
import logging
import string

import app_identity

from flask import request
from werkzeug.exceptions import BadRequest, Forbidden, Unauthorized

SCOPE = 'https://www.googleapis.com/auth/userinfo.email'
EPOCH = datetime.datetime.utcfromtimestamp(0)

# Role constants; used with role_whitelist in auth_required below.
PTC = "ptc"
HEALTHPRO = "healthpro"
PTC_AND_HEALTHPRO = [PTC, HEALTHPRO]
ALL_ROLES = [PTC, HEALTHPRO]


def auth_required(role_whitelist):
    """A decorator that keeps the function from being called without auth.
    role_whitelist can be a string or list of strings specifying one or
    more roles that are allowed to call the function. """

    assert role_whitelist, "Can't call `auth_required` with empty role_whitelist."

    if type(role_whitelist) != list:
        role_whitelist = [role_whitelist]

    def auth_required_wrapper(func):
        def wrapped(*args, **kwargs):
            appid = app_identity.get_application_id()
            # Only enforce HTTPS and auth for external requests; requests made for data generation
            # are allowed through (when enabled).
            if not _is_self_request():
                if request.scheme.lower() != 'https' and appid not in ('None', 'testbed-test', 'testapp'):
                    raise Unauthorized('HTTPS is required for %r' % appid)
                check_auth(role_whitelist)
            return func(*args, **kwargs)

        return wrapped

    return auth_required_wrapper


def auth_required_cron(func):
    """A decorator that ensures that the user is a cron job."""

    def wrapped(*args, **kwargs):
        check_cron()
        return func(*args, **kwargs)

    return wrapped


def nonprod(func):
    """The decorated function may never run in environments without config.ALLOW_NONPROD_REQUESTS."""

    def wrapped(*args, **kwargs):
        if not config.getSettingJson(config.ALLOW_NONPROD_REQUESTS, False):
            raise Forbidden('Request not allowed in production environment (according to config).')
        return func(*args, **kwargs)

    return wrapped


def check_auth(role_whitelist):
    """Raises Unauthorized or Forbidden if the current user is not allowed."""
    user_email, user_info = get_validated_user_info()

    if set(user_info.get('roles', [])) & set(role_whitelist):
        return

    logging.info('User {} has roles {}, but {} is required'.format(
        user_email,
        user_info.get('roles'),
        role_whitelist))
    raise Forbidden()


def get_oauth_id():
    """Returns user email ID if OAUTH token present, or None."""
    try:
        user_email = oauth.get_current_user(SCOPE).email()
    except oauth.Error as e:
        user_email = None
        logging.error('OAuth failure: {}'.format(e))
    return user_email


def check_cron():
    """Raises Forbidden if the current user is not a cron job."""
    if request.headers.get('X-Appengine-Cron'):
        logging.info('Appengine-Cron ALLOWED for cron endpoint.')
        return
    logging.info('User {} NOT ALLOWED for cron endpoint'.format(
        get_oauth_id()))
    raise Forbidden()


def lookup_user_info(user_email):
    return config.getSettingJson(config.USER_INFO, {}).get(user_email)


def _is_self_request():
    return (request.remote_addr is None
            and config.getSettingJson(config.ALLOW_NONPROD_REQUESTS, False)
            and not request.headers.get('unauthenticated'))


def get_validated_user_info():
    """Returns a valid (user email, user info), or raises Unauthorized or Forbidden."""
    user_email = get_oauth_id()

    # Allow clients to simulate an unauthentiated request (for testing)
    # becaues we haven't found another way to create an unauthenticated request
    # when using dev_appserver. When client tests are checking to ensure that an
    # unauthenticated requests gets rejected, they helpfully add this header.
    # The `application_id` check ensures this feature only works in dev_appserver.
    if request.headers.get('unauthenticated') and app_identity.get_application_id() == 'None':
        user_email = None
    if user_email is None:
        raise Unauthorized('No OAuth user found.')

    user_info = lookup_user_info(user_email)
    if user_info:
        enforce_ip_whitelisted(request.remote_addr, get_whitelisted_ips(user_info))
        enforce_appid_whitelisted(request.headers.get('X-Appengine-Inbound-Appid'),
                                  get_whitelisted_appids(user_info))
        logging.info('User %r ALLOWED', user_email)
        return (user_email, user_info)

    logging.info('User %r NOT ALLOWED' % user_email)
    raise Forbidden()


def get_whitelisted_ips(user_info):
    if not user_info.get('whitelisted_ip_ranges'):
        return None
    return [netaddr.IPNetwork(rng)
            for rng in user_info['whitelisted_ip_ranges']['ip6'] + \
            user_info['whitelisted_ip_ranges']['ip4']]


def enforce_ip_whitelisted(request_ip, whitelisted_ips):
    if whitelisted_ips == None:  # No whitelist means "don't apply restrictions"
        return
    logging.info('IP RANGES ALLOWED: {}'.format(whitelisted_ips))
    ip = netaddr.IPAddress(request_ip)
    if not bool([True for rng in whitelisted_ips if ip in rng]):
        logging.info('IP {} NOT ALLOWED'.format(ip))
        raise Forbidden('Client IP not whitelisted: {}'.format(ip))
    logging.info('IP {} ALLOWED'.format(ip))


def get_whitelisted_appids(user_info):
    return user_info.get('whitelisted_appids')


def enforce_appid_whitelisted(request_app_id, whitelisted_appids):
    if not whitelisted_appids:  # No whitelist means "don't apply restrictions"
        return
    if request_app_id:
        if request_app_id in whitelisted_appids:
            logging.info('APP ID {} ALLOWED'.format(request_app_id))
            return
        else:
            logging.info('APP ID {} NOT FOUND IN {}'.format(request_app_id, whitelisted_appids))
    else:
        logging.info('NO APP ID FOUND WHEN REQUIRED TO BE ONE OF: {}'.format(whitelisted_appids))
    raise Forbidden()


def update_model(old_model, new_model):
    """Updates a model.
    For all fields that are set in new_model, copy them into old_model.

    Args:
      old_model: The ndb model object retrieved from the datastore.
      new_model_dict: A json object containing the new values.
    """

    for k, v in new_model.to_dict().items():
        if type(getattr(type(new_model), k)) != ndb.ComputedProperty and v is not None:
            setattr(old_model, k, v)


def format_json_date(obj, field_name, date_format=None):
    """Converts a field of a dictionary from a datetime to a string."""
    if field_name in obj:
        if obj[field_name] is None:
            del obj[field_name]
        else:
            if date_format:
                obj[field_name] = obj[field_name].strftime(date_format)
            else:
                obj[field_name] = obj[field_name].isoformat()


def format_json_code(obj, field_name):
    field_without_id = field_name[0:len(field_name) - 2]
    value = obj.get(field_name)
    if value:
        from dao.code_dao import CodeDao
        code = CodeDao().get(value)
        if code.mapped:
            obj[field_without_id] = code.value
        else:
            obj[field_without_id] = UNMAPPED
        del obj[field_name]
    else:
        obj[field_without_id] = UNSET


def format_json_hpo(obj, field_name):
    if obj[field_name]:
        from dao.hpo_dao import HPODao
        obj[field_name] = HPODao().get(obj[field_name]).name
    else:
        obj[field_name] = UNSET


def unix_time_millis(dt):
    return int((dt - EPOCH).total_seconds() * 1000)


def parse_json_enum(obj, field_name, enum_cls):
    """Converts a field of a dictionary from a string to an enum."""
    if field_name in obj and obj[field_name] is not None:
        obj[field_name] = enum_cls(obj[field_name])


def format_json_enum(obj, field_name):
    """Converts a field of a dictionary from a enum to an string."""
    if field_name in obj and obj[field_name] is not None:
        obj[field_name] = str(obj[field_name])
    else:
        obj[field_name] = UNSET


def remove_field(dict_, field_name):
    """Removes a field from the dict if it exists."""
    if field_name in dict_:
        del dict_[field_name]


def searchable_representation(str_):
    """Takes a string, and returns a searchable representation.

    The string is lowercased and punctuation is removed.
    """
    if not str_:
        return str_

    str_ = str(str_)
    return str_.lower().translate(None, string.punctuation)
