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

String fixture(String name) => File('test/fixtures/$name.json').readAsStringSync();

class FakeArgus {
  final List<http.Request> requests = [];

  /// Replace every response with this one (to simulate revocation, an old client, an outage).
  http.Response? override;

  late final http.Client client = MockClient((req) async {
    requests.add(req);
    return _serve(req);
  });

  http.Response _serve(http.Request req) {
    if (override != null) return override!;
    final p = req.url.path;
    final q = req.url.queryParameters;
    String? name;
    int status = 200;
    if (req.method == 'POST' && p == '/v1/devices') {
      name = 'device';
    } else {
      name = switch (p) {
        '/v1/me' => 'me',
        '/v1/me/workspaces' => 'workspaces',
        '/v1/meta/api' => 'meta',
        '/v1/hub/search' => 'search',
        '/v1/assets/$positionUid' => 'position',
        '/v1/hub/assets/$positionUid/context' => 'position_context',
        '/v1/installations' when q['position_uid'] == positionUid => 'position_installations',
        '/v1/issues/$ticketUid' => 'ticket',
        '/v1/documents/$documentUid' => 'document',
        '/v1/documents/$documentUid/current' => 'document_current',
        '/v1/documents/$draftUid' => 'draft',
        '/v1/documents/$draftUid/current' => 'draft_current',
        '/v1/links/resolve' when q['path'] == '/position/$positionUid' => 'resolve_position',
        _ => null,
      };
      if (name == 'draft_current') status = 404;
    }
    if (name == null) {
      return http.Response(jsonEncode({'detail': {'error': 'Not found, or not visible to you.', 'code': 'not_found'}}), 404,
          headers: {'content-type': 'application/json'});
    }
    return http.Response.bytes(utf8.encode(fixture(name)), status,
        headers: {'content-type': 'application/json; charset=utf-8'});
  }

  static http.Response problem(int status, String code, {String error = 'refused', String? minimum}) => http.Response(
      jsonEncode({'detail': {'error': error, 'code': code, 'minimum': ?minimum}}), status,
      headers: {'content-type': 'application/json'});
}
