import json
from aiohttp import web
import logging
import json

# Content-Type
CONTENT_TYPE = 'Content-Type'
CONTENT_TYPE_HTML = {'Content-Type': 'text/html'}
CONTENT_TYPE_JSON = {'Content-Type': 'application/json'}


async def content_type_json_check(request):
    if request.content_type != 'application/json':
        raise TypeError('Content-Type is application/json,'
                        ' not {}'.format(request.content_type))
    else:
        try:
            return await request.json()
        except json.JSONDecodeError:
            # POST method check, but No body found
            body = await request.text()
            logging.error("content_type_json_check() body={}".format(body))


def json_res(data, indent=4):
    return web.Response(
        text=json.dumps(data, indent=indent),
        content_type='application/json')


def error_res(errors=None):
    if errors:
        import traceback
        errors = str(traceback.format_exc())
    return web.Response(text=errors, status=400)
