"""
licenses_api.py — SPDX license list endpoint.
"""
from flask import request
from flask_restx import Namespace, Resource

from ..core.utils.decorators import api_require_permission
from ..core.utils.licenses import search_licenses, get_licenses

licenses_ns = Namespace('licenses', description='SPDX license list')


@licenses_ns.route('/')
class LicenseList(Resource):

    @api_require_permission(None)   # any authenticated user
    def get(self):
        """
        Search SPDX license identifiers.

        Query params:
          search  (str)  — substring / prefix filter
          limit   (int)  — max results (default 30, max 200)
        """
        q     = request.args.get('search', '').strip()
        limit = min(200, max(1, int(request.args.get('limit', 30))))
        items = search_licenses(q, limit)
        return {'licenses': items, 'total': len(get_licenses())}, 200
