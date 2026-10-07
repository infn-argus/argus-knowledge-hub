import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

/// Responses recorded from a real ARGUS API (see test/fixtures/README.md), served by path.
const positionUid = 'b3bc26da-32af-4d88-9551-612592db3359';
const ticketUid = '3ad8eae6-5a19-4c15-9e2e-be4ab4b6f983';
const documentUid = '1ee032b4-5a00-4716-a269-8adce879fd8c';
const draftUid = 'a0f68206-97f9-49cd-9fb8-f3f0fd322f6c';
const workspaceId = 'slice-20463f';
const recordedUnit = '506c63d7-f353-4b5f-9e6d-a0528d4e679f';
const recordedInstallation = 'a54b9136-c75f-4840-9d0e-1830186774dc';
const incomingUnit = '812ddce6-b3a6-4d69-8e23-4e3600136faa';
const ionPumpUid = 'd2b1c2d3-1234-4a5b-8c9d-0e1f2a3b4c5d';

String fixture(String name) => File('test/fixtures/$name.json').readAsStringSync();
Object? fixtureJson(String name) => jsonDecode(fixture(name));

http.Response _json(Object? body, [int status = 200]) => http.Response.bytes(
    utf8.encode(body is String ? body : jsonEncode(body)), status,
    headers: {'content-type': 'application/json; charset=utf-8'});

class FakeArgus {
  final List<http.Request> requests = [];

  /// Replace every response with this one (to simulate revocation, an old client, an outage).
  http.Response? override;

  /// Replace the response of one route: `'POST /v1/issues/<uid>/transition'`.
  final Map<String, http.Response> routes = {};

  final Map<String, int> _uploads = {};

  /// No network: every request fails as if the device were out of reach.
  bool offline = false;

  /// Serve these once, then lose the answer (the request reached the server; the reply did not).
  final Set<String> loseAnswer = {};

  late final http.Client client = MockClient((req) async {
    if (offline) throw http.ClientException('Network is unreachable', req.url);
    requests.add(req);
    if (loseAnswer.remove('${req.method} ${req.url.path}')) {
      throw http.ClientException('Connection reset after the request was sent', req.url);
    }
    if (override != null) return override!;
    return routes['${req.method} ${req.url.path}'] ?? _serve(req);
  });

  /// The JSON bodies sent to a route, in order.
  List<Map<String, dynamic>> sent(String method, String path) => [
        for (final r in requests)
          if (r.method == method && r.url.path == path && r.body.isNotEmpty) jsonDecode(r.body) as Map<String, dynamic>,
      ];

  http.Response _serve(http.Request req) {
    final p = req.url.path;
    final q = req.url.queryParameters;
    final m = req.method;
    Map<String, dynamic> body() => req.body.isEmpty ? {} : jsonDecode(req.body) as Map<String, dynamic>;

    if (m == 'POST') {
      switch (p) {
        case '/v1/devices':
          return _json(fixture('device'));
        case '/v1/intake/assist/ticket':
          return _json(fixture('assist_ticket'));
        case '/v1/intake/assist/asset/file':
          return _json(fixture('assist_asset_photo'));
        case '/v1/intake/guide/asset':
          return _json(fixture('guide_asset'));
        case '/v1/intake/guide/ticket':
          // Like the real guide: what the draft already says is not asked again.
          final draft = (body()['draft'] as Map?) ?? {};
          final attrs = (draft['attributes'] as Map?) ?? {};
          final g = fixtureJson('guide_ticket') as Map<String, dynamic>;
          g['checks'] = [
            for (final c in g['checks'] as List)
              if (!(c['field'] == 'attributes.occurred_from' && attrs['occurred_from'] != null) &&
                  !(c['id'] == 'description' && ((draft['description'] as String?) ?? '').length >= 20))
                c,
          ];
          return _json(g);
        case '/v1/issues':
          final b = body();
          final t = fixtureJson('ticket_created') as Map<String, dynamic>;
          return _json({...t, 'uid': b['uid'], 'title': b['title'], 'asset_uid': b['asset_uid']}, 201);
        case '/v1/uploads':
          final uid = 'up-${_uploads.length + 1}';
          _uploads[uid] = 0;
          return _json({'uid': uid, 'offset': 0, 'state': 'open', 'size': body()['size']}, 201);
        case '/v1/assets':
          final b = body();
          final a = fixtureJson('position') as Map<String, dynamic>;
          return _json({...a, 'uid': b['uid'], 'name': b['name'], 'schema_uid': b['schema_uid'],
            'attributes': b['attributes']}, 201);
      }
      if (p == '/v1/installations/replace') {
        final b = body();
        final mismatch = b['outgoing_uid'] != recordedUnit;
        if (b['dry_run'] == true) return _json(fixture(mismatch ? 'replace_preview_mismatch' : 'replace_preview'));
        if (mismatch) return _json(fixture('replace_proposed'), 202);
        return _json({'outcome': 'applied', 'reasons': [], 'ended': [recordedInstallation], 'installation_uid': 'inst-new'});
      }
      if (RegExp(r'^/v1/ledger/review/(replacements|stale)/[^/]+/(confirm|reject|close)$').hasMatch(p) ||
          RegExp(r'^/v1/intake/proposals/[^/]+$').hasMatch(p)) {
        return _json({'ok': true, 'outcome': 'applied'});
      }
      if (RegExp(r'^/v1/intake/runs/[^/]+/outcome$').hasMatch(p)) return _json({'ok': true}, 201);
      if (RegExp(r'^/v1/issues/[^/]+/comments$').hasMatch(p)) {
        final c = fixtureJson('comment_created') as Map<String, dynamic>;
        return _json({...c, 'uid': body()['uid'], 'body': body()['body']}, 201);
      }
      if (RegExp(r'^/v1/assets/[^/]+/comments$').hasMatch(p)) {
        final b = body();
        return _json({'uid': b['uid'], 'asset_uid': p.split('/')[3], 'author': b['author'], 'text': b['text'],
          'created': b['created'], 'updated': b['updated']}, 201);
      }
      if (RegExp(r'^/v1/issues/[^/]+/transition$').hasMatch(p)) return _json(fixture('ticket'));
      if (RegExp(r'^/v1/notifications/\d+/read$').hasMatch(p)) return _json({'ok': true});
      final upload = RegExp(r'^/v1/uploads/([^/]+)/(complete|attach/(ticket|asset)/.+)$').firstMatch(p);
      if (upload != null) {
        final attach = upload.group(2)!.startsWith('attach');
        return _json({'uid': upload.group(1), 'state': attach ? 'attached' : 'complete',
          if (attach) 'attachment_uid': 'att-${upload.group(1)}'});
      }
    }
    if (m == 'PUT' && RegExp(r'^/v1/assets/[^/]+$').hasMatch(p)) {
      final a = fixtureJson('position') as Map<String, dynamic>;
      return _json({...a, 'attributes': body()['attributes'] ?? a['attributes']});
    }
    if (m == 'PUT' && p.startsWith('/v1/uploads/')) {
      final uid = p.split('/').last;
      final offset = int.parse(q['offset']!);
      if (offset != _uploads[uid]) {
        return _json({'detail': 'x', 'problem': {'code': 'conflict', 'error': 'wrong offset',
          'current': {'offset': _uploads[uid]}}}, 409);
      }
      _uploads[uid] = offset + req.bodyBytes.length;
      return _json({'uid': uid, 'offset': _uploads[uid], 'state': 'open'});
    }

    String? name;
    int status = 200;
    name = switch (p) {
      '/v1/me' => 'me',
      '/v1/me/workspaces' => 'workspaces',
      '/v1/meta/api' => 'meta',
      '/v1/hub/search' => 'search',
      '/v1/schemas' => 'schemas',
      '/v1/notifications' => 'notifications',
      '/v1/assets/$positionUid' => 'position',
      '/v1/hub/assets/$positionUid/context' => 'position_context',
      '/v1/assets/$ionPumpUid' => 'ion_pump',
      '/v1/hub/assets/$ionPumpUid/context' => 'ion_pump_context',
      '/v1/installations' when q['position_uid'] == positionUid => 'position_installations',
      '/v1/issues/$ticketUid' => 'ticket',
      '/v1/documents/$documentUid' => 'document',
      '/v1/documents/$documentUid/current' => 'document_current',
      '/v1/documents/$draftUid' => 'draft',
      '/v1/documents/$draftUid/current' => 'draft_current',
      '/v1/links/resolve' when q['path'] == '/position/$positionUid' => 'resolve_position',
      '/v1/ledger/review/mine' => 'review_mine',
      _ => null,
    };
    if (name == 'draft_current') status = 404;
    if (m == 'GET' && p == '/v1/links/resolve' && q['path'] == '/lookup/IP-NEW-1') {
      return _json({'kind': 'asset', 'uid': incomingUnit, 'key': 'SLICE-20463F-IP-0001', 'name': 'Ion pump gun area 2',
        'type': 'Ion Pump', 'web_path': '/assets/$incomingUnit'});
    }
    if (name == null && m == 'GET') {
      if (RegExp(r'^/v1/issues/[^/]+/comments$').hasMatch(p)) return _json(fixture('comments'));
      if (RegExp(r'^/v1/issues/[^/]+/attachments$').hasMatch(p)) return _json([]);
      if (RegExp(r'^/v1/assets/[^/]+/comments$').hasMatch(p)) return _json(fixture('asset_comments'));
      if (RegExp(r'^/v1/assets/[^/]+/history$').hasMatch(p)) return _json(fixture('asset_history'));
      if (p == '/v1/assets' && q['schema_uid'] == 'slice-20463f:argus-object:product-model') {
        return _json(fixture('product_models'));
      }
      final productModel = RegExp(r'^/v1/assets/(pm-[^/]+)$').firstMatch(p);
      if (productModel != null) {
        final rows = fixtureJson('product_models') as List;
        final row = rows.cast<Map<String, dynamic>>().firstWhere((r) => r['uid'] == productModel.group(1));
        return _json(row);
      }
      final productModelContext = RegExp(r'^/v1/hub/assets/(pm-[^/]+)/context$').firstMatch(p);
      if (productModelContext != null) {
        final rows = fixtureJson('product_models') as List;
        final row = rows.cast<Map<String, dynamic>>().firstWhere((r) => r['uid'] == productModelContext.group(1));
        return _json({
          'asset': {'uid': row['uid'], 'key': row['key'], 'name': row['name'], 'type': row['type'],
            'schema_uid': row['schema_uid'], 'workspace_id': row['workspace_id']},
          'nature': 'equipment', 'processing': null, 'restricted': null, 'merged': null,
          'type_path': ['Product Model'], 'access': {'tickets': true, 'documents': true},
          'stats': {'open_tickets': 0, 'tickets': 0, 'external_tickets': 0, 'documents': 0, 'documents_overdue': 0, 'relations': 0},
          'tickets': [], 'external_tickets': [], 'documents': [], 'relations': {'total': 0, 'by_relation': {}, 'items': []},
        });
      }
      if (p == '/v1/attachments' && q['asset_uid'] == positionUid) return _json(fixture('asset_attachments'));
      if (p == '/v1/attachments' && q['asset_uid'] == ionPumpUid) return _json([]);
      if (RegExp(r'^/v1/issues/[^/]+/transitions$').hasMatch(p)) return _json(fixture('transitions'));
      final issue = RegExp(r'^/v1/issues/([0-9a-f-]{36})$').firstMatch(p);
      if (issue != null) {
        final t = fixtureJson('ticket_created') as Map<String, dynamic>;
        return _json({...t, 'uid': issue.group(1)});
      }
    }
    if (name == null) {
      return _json({'detail': {'error': 'Not found, or not visible to you.', 'code': 'not_found'}}, 404);
    }
    return _json(fixture(name), status);
  }

  static http.Response problem(int status, String code, {String error = 'refused', String? minimum}) => http.Response(
      jsonEncode({'detail': {'error': error, 'code': code, 'minimum': ?minimum}}), status,
      headers: {'content-type': 'application/json'});
}
