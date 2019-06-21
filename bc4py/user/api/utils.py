from aiohttp import web
from logging import getLogger
import json

log = getLogger('bc4py')

# Content-Type
CONTENT_TYPE = 'Content-Type'
CONTENT_TYPE_HTML = {'Content-Type': 'text/html'}
CONTENT_TYPE_JSON = {'Content-Type': 'application/json'}


async def content_type_json_check(request):
    """check message is json, used for POST method"""
    if request.content_type != 'application/json':
        raise TypeError(f"Content-Type is application/json, not {request.content_type}")
    else:
        try:
            return await request.json()
        except json.JSONDecodeError:
            # POST method check, but No body found
            body = await request.text()
            log.error("content_type_json_check() body={}".format(body))


def json_res(data, indent=4):
    """return json response with indent"""
    res = web.Response(text=json.dumps(data, indent=indent), content_type='application/json')
    res.enable_compression()
    return res


def error_res(errors=None):
    """simple error message response"""
    if errors is None:
        import traceback
        errors = str(traceback.format_exc())
    log.info(f"API error:\n{errors}")
    s = errors.split("\n")
    simple_msg = None
    while not simple_msg:
        simple_msg = s.pop(-1)
    return web.Response(text=simple_msg + '\n', status=400)
