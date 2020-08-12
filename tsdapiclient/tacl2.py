
import getpass
import os
import platform
import sys

from textwrap import dedent

import click
import requests

from tsdapiclient import __version__
from tsdapiclient.administrator import get_tsd_api_key
from tsdapiclient.authapi import get_jwt_tsd_auth, get_jwt_basic_auth
from tsdapiclient.client_config import ENV
from tsdapiclient.configurer import (
    read_config, update_config, print_config, delete_config
)
from tsdapiclient.fileapi import (
    streamfile, initiate_resumable, get_resumable, delete_resumable,
    delete_all_resumables, export_get, export_list,
    print_export_list, print_resumables_list
)
from tsdapiclient.session import (
    session_is_expired, session_expires_soon, session_update,
    session_clear, session_token
)
from tsdapiclient.tools import user_agent, debug_step

requests.utils.default_user_agent = user_agent

API_ENVS = {
    'prod': 'api.tsd.usit.no',
    'alt': 'alt.api.tsd.usit.no',
    'test': 'test.api.tsd.usit.no'
}


def print_version_info():
    version_text = """\
        tacl v{version}
        - OS/Arch: {os}/{arch}
        - Python: {pyver}\
    """.format(
        version=__version__,
        os=platform.system(),
        arch=platform.uname().machine,
        pyver=platform.python_version()
    )
    print(dedent(version_text))

def get_api_envs(ctx, args, incomplete):
    return [k for k, v in API_ENVS.items() if incomplete in k]


def get_user_credentials():
    username = input('username > ')
    password = getpass.getpass('password > ')
    otp = input('one time code > ')
    return username, password, otp


def get_api_key(env, pnum):
    config = read_config()
    if not config:
        print('client not registered')
        sys.exit(1)
    api_key = config.get(env, {}).get(pnum)
    if not api_key:
        print(f'client not registered for API environment {env} and {pnum}')
        sys.exit(1)
    try:
        has_exired = check_if_key_has_expired(api_key)
        if has_exired:
            print('Your API key has expired')
            print('Register your client again')
            sys.exit(1)
    except Exception:
        pass
    return api_key


@click.command()
@click.argument(
    'pnum',
    required=False,
    default=None
)
@click.option(
    '--guide',
    is_flag=True,
    required=False,
    help='Print a guide'
)
@click.option(
    '--env',
    default='prod',
    help='API environment',
    show_default=True,
    autocompletion=get_api_envs
)
@click.option(
    '--group',
    required=False,
    help='Choose which file group should own the data import'
)
@click.option(
    '--basic',
    is_flag=True,
    required=False,
    help='When using basic auth, specify the TSD project'
)
@click.option(
    '--upload',
    default=None,
    required=False,
    help='Import a file or a directory located at given path'
)
@click.option(
    '--upload-id',
    default=None,
    required=False,
    help='Identifies a specific resumable upload'
)
@click.option(
    '--resume-list',
    is_flag=True,
    required=False,
    help='List all resumable uploads'
)
@click.option(
    '--resume-delete',
    default=None,
    required=False,
    help='Delete a specific resumable upload'
)
@click.option(
    '--resume-delete-all',
    is_flag=True,
    required=False,
    help='Delete all resumable uploads'
)
@click.option(
    '--download',
    is_flag=True,
    required=False,
    help='Download a file'
)
@click.option(
    '--download-list',
    is_flag=True,
    required=False,
    help='List files available for download'
)
@click.option(
    '--download-id',
    default=None,
    required=False,
    help='Identifies a download which can be resumed'
)
@click.option(
    '--version',
    is_flag=True,
    required=False,
    help='Show tacl version info'
)
@click.option(
    '--verbose',
    is_flag=True,
    required=False,
    help='Run tacl in verbose mode'
)
@click.option(
    '--config-show',
    is_flag=True,
    required=False,
    help='Show tacl config'
)
@click.option(
    '--config-delete',
    is_flag=True,
    required=False,
    help='Delete tacl config'
)
@click.option(
    '--session-delete',
    is_flag=True,
    required=False,
    help='Delete current tacl login session'
)
@click.option(
    '--register',
    is_flag=True,
    required=False,
    help='Register tacl for a specific TSD project and API environment'
)
def cli(
    pnum,
    guide,
    env,
    group,
    basic,
    upload,
    upload_id,
    resume_list,
    resume_delete,
    resume_delete_all,
    download,
    download_id,
    download_list,
    version,
    verbose,
    config_show,
    config_delete,
    session_delete,
    register
):
    """tacl2 - TSD API client."""
    token = None
    if verbose:
        os.environ['DEBUG'] = '1'
    if upload or resume_list or resume_delete or resume_delete_all:
        if basic:
            requires_user_credentials, token_type = False, 'import'
        else:
            requires_user_credentials, token_type = True, 'import'
    elif download or download_list:
        if basic:
            click.echo('download not authorized with basic auth')
            sys.exit(1)
        requires_user_credentials, token_type = True, 'export'
    else:
        requires_user_credentials = False
    if requires_user_credentials:
        if not pnum:
            click.echo('missing pnum argument')
            sys.exit(1)
        auth_required = False
        debug_step(f'using login session with {env}:{pnum}:{token_type}')
        debug_step('checking if login session has expired')
        expired = session_is_expired(env, pnum, token_type)
        if expired:
            click.echo('your session has expired, please authenticate')
            auth_required = True
        debug_step('checking if login session will expire soon')
        expires_soon = session_expires_soon(env, pnum, token_type)
        if expires_soon:
            click.echo('your session expires soon')
            if click.confirm('Do you want to refresh your login session?'):
                auth_required = True
            else:
                auth_required = False
        if not expires_soon and expired:
            auth_required = True
        if auth_required:
            api_key = get_api_key(env, pnum)
            username, password, otp = get_user_credentials()
            token = get_jwt_tsd_auth(env, pnum, api_key, username, password, otp, token_type)
            if token:
                debug_step('updating login session')
                session_update(env, pnum, token_type, token)
        else:
            debug_step(f'using token from existing login session')
            token = session_token(env, pnum, token_type)
    elif not requires_user_credentials and basic:
        if not pnum:
            click.echo('missing pnum argument')
            sys.exit(1)
        api_key = get_api_key(env, pnum)
        debug_step('using basic authentication')
        token = get_jwt_basic_auth(env, pnum, api_key)
    if (requires_user_credentials or basic) and not token:
        click.echo('authentication failed')
        sys.exit(1)
    if token:
        if upload:
            group = f'{pnum}-member-group' if not group else group
            chunk_size = os.stat(upload).st_size
            if upload_id or os.stat(upload).st_size > 1000*1000*1000:
                chunk_size = 1000*1000*50
                resp = initiate_resumable(
                    env, pnum, upload, token, chunksize=chunk_size,
                    group=group, verify=True, upload_id=upload_id
                )
            else:
                resp = streamfile(
                    env, pnum, upload, token, group=group
                )
        elif resume_list:
            debug_step('listing resumables')
            overview = get_resumable(env, pnum, token)
            print_resumables_list(overview)
        elif resume_delete:
            filename = resume_delete
            debug_step('deleting resumable')
            delete_resumable(env, pnum, token, filename, upload_id)
        elif resume_delete_all:
            debug_step('deleting all resumables')
            delete_all_resumables(env, pnum, token)
        elif download:
            filename = download
            debug_step('starting file export')
            export_get(env, pnum, filename, token, etag=download_id)
        elif download_list:
            debug_step('listing export directory')
            data = export_list(env, pnum, token)
            print_export_list(data)
        return
    else:
        if config_show:
            print_config()
        elif config_delete:
            delete_config()
        elif session_delete:
            session_clear()
        elif register:
            prod = "1 - for normal production usage"
            fx = "2 - for use over fx03 network"
            test = "3 - for testing"
            prompt = "Choose the API environment by typing one of the following numbers"
            choice = input(f"""{prompt}:\n{prod}\n{fx}\n{test} > """)
            if choice not in '123':
                click.echo(f'Invalid choice: {choice} for API environment')
                sys.exit(1)
            choices = {'1': 'prod', '2': 'alt', '3': 'test'}
            env = choices[choice]
            username, password, otp = get_user_credentials()
            pnum = username.split('-')[0]
            key = get_tsd_api_key(env, pnum, username, password, otp)
            update_config(env, pnum, key)
            click.echo(f'Successfully registered for {pnum}, and API environment hosted at {ENV[env]}')
        elif version:
            print_version_info()
        return


if __name__ == '__main__':
    cli()
