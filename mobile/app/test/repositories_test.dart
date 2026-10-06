import 'dart:convert';

import 'package:argus_field/core/config.dart';
import 'package:argus_field/core/problem.dart';
import 'package:argus_field/core/session.dart';
import 'package:argus_field/data/api_service.dart';
import 'package:argus_field/data/capture_repositories.dart';
import 'package:argus_field/data/repositories.dart';
import 'package:argus_field/domain/models.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fake_server.dart';

void main() {
  late FakeArgus server;
  late ApiService api;
  final problems = <Problem>[];
  const config = AppConfig(
    environment: 'development',
    apiBase: 'https://argus.test/',
    linkHost: 'argus.test',
    oidcIssuer: '',
    oidcClientId: '',
    oidcRedirect: '',
    appVersion: '0.1.0',
  );
  const session = Session(accessToken: 'tok', authType: 'token', workspaceId: workspaceId, deviceId: 'dev-1');

  setUp(() {
    server = FakeArgus();
    problems.clear();
    api = ApiService(config, () => session, httpClient: server.client, onProblem: problems.add);
  });

  test('every request carries the token, the workspace, the client version and the device', () async {
    await WorkspaceRepository(api).mine();
    final h = server.requests.single.headers;
    expect(h['Authorization'], 'Bearer tok');
    expect(h['X-Workspace-Id'], workspaceId);
    expect(h['X-ARGUS-Device'], 'dev-1');
    expect(h['X-ARGUS-Client'], startsWith('flutter/0.1.0/'));
    expect(server.requests.single.url.toString(), startsWith('https://argus.test/v1/'));
  });

  test('a Position shows what is installed there now, its open tickets and its documents', () async {
    final a = await AssetRepository(api).detail(positionUid);
    expect(a.isPosition, isTrue);
    expect(a.key, 'S7C415E:POS:GUNSIP01');
    expect(a.current.single.asset!.label, 'S7C415EINV-84321 · Ion pump 84321');
    expect(a.current.single.from!.precision, 'day');
    expect(a.tickets.where((t) => t.open).single.title, 'Pressure spike on gun ion pump');
    expect(a.documents.map((d) => d.code), containsAll(['DOC-0001', 'DOC-0002']));
  });

  test('a Position names its schema and what it connects to, in and out', () async {
    final a = await AssetRepository(api).detail(positionUid);
    expect(a.schemaUid, 'slice-20463f:ledger:equipment-position');
    expect(a.avatarIconUid, isNull);
    expect(a.relations, hasLength(2));
    expect(a.inbound.map((r) => r.relation), containsAll(['acts on', 'installed at']));
    expect(a.inbound.first.direction, 'in');
    expect(a.outbound, isEmpty); // the fixture carries only inbound edges
  });

  test("a record's comments, history and files are three separate, independently-refreshable calls", () async {
    final repo = AssetRepository(api);
    final comments = await repo.comments(positionUid);
    expect(comments.single.author, 'ops@slice-20463f.test');
    expect(comments.single.body, contains('controller card'));
    final history = await repo.history(positionUid);
    expect(history.single.type, 'migrated');
    final files = await repo.attachments(positionUid);
    expect(files.single.filename, 'nameplate.jpg');
    expect(files.single.mimeType, 'image/jpeg');
  });

  test('a comment carries its own author and moment, the same way the web app sends one', () async {
    await AssetRepository(api).comment(positionUid, 'c-new', 'field.app@slice-20463f.test', 'Checked, nominal.');
    final sent = server.sent('POST', '/v1/assets/$positionUid/comments').single;
    expect(sent['author'], 'field.app@slice-20463f.test');
    expect(sent['text'], 'Checked, nominal.');
    expect(sent['uid'], 'c-new');
  });

  test("saving an edit sends the record's version as If-Match", () async {
    await AssetRepository(api).save(positionUid, {'position_class': 'Vacuum Gauge'}, version: 3, key: 'edit-1');
    final req = server.requests.last;
    expect(req.method, 'PUT');
    expect(req.headers['If-Match'], '"3"');
    expect(jsonDecode(req.body)['attributes'], {'position_class': 'Vacuum Gauge'});
  });

  test("a type's attributes include its ancestor's, overridden by its own on the same key", () async {
    final defs = await SchemaRepository(api).effectiveAttributes('slice-20463f:argus-object:ion-pump');
    expect(defs.map((d) => d.key), containsAll(['pumping_speed', 'nominal_voltage', 'element_count']));
    final speed = defs.firstWhere((d) => d.key == 'pumping_speed');
    expect(speed.type, 'float');
    expect(speed.editable, isTrue);
    final gauge = await SchemaRepository(api).effectiveAttributes('slice-20463f:argus-object:vacuum-gauge');
    final kind = gauge.firstWhere((d) => d.key == 'gauge_kind');
    expect(kind.options.map((o) => o.value), contains('Pirani'));
  });

  test('an approved document is approved; a draft has nothing to work from', () async {
    final d = await DocumentRepository(api).detail(documentUid);
    expect(d.approved, isTrue);
    expect(d.revisionNumber, 1);
    final draft = await DocumentRepository(api).detail(draftUid);
    expect(draft.revisionState, isNull);
    expect(draft.approved, isFalse);
  });

  test('a link is resolved by the server, which says it is a Position', () async {
    final t = await LookupRepository(api).resolveLink('/position/$positionUid');
    expect(t.kind, RecordKind.position);
    expect(t.route, '/asset/$positionUid');
  });

  test('a missing or invisible record is one problem: not found', () async {
    await expectLater(LookupRepository(api).lookup('NOPE-1'),
        throwsA(isA<Problem>().having((p) => p.code, 'code', ProblemCode.notFound)));
  });

  test('revocation and an old client are reported to the listener', () async {
    server.override = FakeArgus.problem(401, 'revoked');
    await expectLater(TicketRepository(api).detail(ticketUid), throwsA(isA<Problem>()));
    server.override = FakeArgus.problem(426, 'client_too_old', minimum: '1.4.0');
    await expectLater(TicketRepository(api).detail(ticketUid), throwsA(isA<Problem>()));
    expect(problems.map((p) => p.code), [ProblemCode.revoked, ProblemCode.clientTooOld]);
    expect(problems.last.minimum, '1.4.0');
  });

  test('search groups assets, tickets and documents', () async {
    final r = await LookupRepository(api).search('GUNSIP');
    expect(r.assets, isNotEmpty);
    expect(r.assets.first.title, contains('GUNSIP'));
    expect(server.requests.single.url.queryParameters['q'], 'GUNSIP');
  });
}
