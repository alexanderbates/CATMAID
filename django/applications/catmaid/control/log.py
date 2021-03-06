# -*- coding: utf-8 -*-

import json
import logging

from django.http import JsonResponse
from django.contrib.auth.decorators import user_passes_test

from catmaid.models import UserRole, Log, ReviewerWhitelist
from catmaid.control.common import get_request_bool
from catmaid.control.authentication import requires_user_role
from catmaid.control.user import access_check

@user_passes_test(access_check)
def log_frontent_event(request, level='info'):
    """ Logs events from the front end if a user is signed in or was assigned
    browse permissions.
    """
    msg = request.POST.get('msg', None)
    if not msg:
        raise ValueError("No message given to log")

    try:
        logger = logging.getLogger('catmaid.frontend')
        entry = "User: %s (%s) %s" % (
            request.user.username, request.user.id, msg)
        result = log(logger, level, entry)
        status = "success"
        status_msg = "Successfully created log entry"
    except Exception as se:
        status = "error"
        status_msg = str(e)

    return JsonResponse({
        'status': status,
        'message': status_msg
    })

def log(logger, level, msg):
    # Cancel silently if handler is not present
    if not logger.handlers:
        return

    if "info" == level:
        logger.info(msg)
    elif "error" == level:
        logger.error(msg)
    elif "debug" == level:
        logger.debug(msg)
    else:
        raise ValueError("Unknown level: " + level)

@requires_user_role([UserRole.Annotate, UserRole.Browse])
def list_logs(request, project_id=None):
    if 'user_id' in request.POST:
        user_id = int(request.POST.get('user_id', -1))  # We can see logs for different users
    else:
        user_id = None
    whitelist = get_request_bool(request.POST, 'whitelist', False)
    operation_type = request.POST.get('operation_type', "-1")
    search_freetext = request.POST.get('search_freetext', "")

    display_start = int(request.POST.get('iDisplayStart', 0))
    display_length = int(request.POST.get('iDisplayLength', -1))
    if display_length < 0:
        display_length = 2000  # Default number of result rows

    should_sort = request.POST.get('iSortCol_0', False)
    if should_sort:
        column_count = int(request.POST.get('iSortingCols', 0))
        sorting_directions = [request.POST.get('sSortDir_%d' % d, 'DESC') for d in range(column_count)]
        sorting_directions = map(lambda d: '-' if d.upper() == 'DESC' else '', sorting_directions)

        fields = ['user', 'operation_type', 'creation_time', 'x', 'y', 'z', 'freetext']
        sorting_index = [int(request.POST.get('iSortCol_%d' % d)) for d in range(column_count)]
        sorting_cols = map(lambda i: fields[i], sorting_index)

    log_query = Log.objects.for_user(request.user).filter(project=project_id)
    if user_id:
        log_query = log_query.filter(user=user_id)
    if whitelist:
        log_query = log_query.filter(user_id__in=ReviewerWhitelist.objects.filter(
                project_id=project_id, user_id=request.user.id).values_list('reviewer_id'))
    if not operation_type == "-1":
        log_query = log_query.filter(operation_type=operation_type)
    if not search_freetext == "":
        log_query = log_query.filter(freetext__contains=search_freetext)

    log_query = log_query.extra(tables=['auth_user'], where=['"log"."user_id" = "auth_user"."id"'], select={
        'x': '("log"."location")."x"',
        'y': '("log"."location")."y"',
        'z': '("log"."location")."z"',
        'username': '"auth_user"."username"'
    })
    if should_sort:
        log_query = log_query.extra(order_by=[di + col for (di, col) in zip(sorting_directions, sorting_cols)])

    result = list(log_query[display_start:display_start + display_length])

    response = {'iTotalRecords': len(result), 'iTotalDisplayRecords': len(result), 'aaData': []}
    for log in result:
        response['aaData'] += [[
            log.username,
            log.operation_type,
            str(log.creation_time.isoformat()),
            log.x,
            log.y,
            log.z,
            log.freetext
        ]]

    return JsonResponse(response)
