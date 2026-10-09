import 'dart:convert';

import 'package:argus_api/api.dart' as api;
import 'package:crypto/crypto.dart' show sha256;
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart' show MediaType;

import '../core/problem.dart';
import '../domain/capture.dart';
import '../domain/models.dart' show AttributeDef;
import 'api_service.dart';

Map<String, Object?> _map(Object? o) => o is Map ? o.map((k, v) => MapEntry(k.toString(), v)) : const {};
List<Object?> _list(Object? o) => o is List ? o : const [];
DateTime? _date(Object? o) => o is String ? DateTime.tryParse(o) : null;

List<GuideCheck> parseChecks(Object? guide) => _list(_map(guide)['checks']).map(_map).map((c) => GuideCheck(
      id: (c['id'] ?? '').toString(),
      level: (c['level'] ?? 'info').toString(),
      message: (c['message'] ?? '').toString(),
      field: c['field']?.toString(),
      links: _list(c['links']).map(_map).map((l) => (
            uid: l['uid'].toString(),
            name: (l['name'] ?? l['key'] ?? '').toString(),
            path: (l['path'] ?? '').toString(),
          )).toList(),
    )).toList();

AssistResult parseAssist(Object? body) {
  final r = _map(body);
  return AssistResult(
    runId: r['run_id'].toString(),
    proposals: _map(r['fields']).map((field, v) {
      final f = _map(v);
      return MapEntry(
          field,
          Proposal(
            field: field,
            value: f['value'],
            label: f['label']?.toString(),
            confidence: (f['confidence'] as num?)?.toDouble(),
            evidence: f['evidence']?.toString(),
            grounded: f['grounded'] != false,
            method: (f['method'] ?? 'ai_extracted').toString(),
          ));
    }),
    dropped: _list(r['dropped']).map(_map).map((d) => Dropped(d['field'].toString(), d['reason'].toString())).toList(),
    hypotheses: _list(r['hypotheses']).map((h) => h is Map ? (h['text'] ?? '').toString() : h.toString()).toList(),
    redacted: (r['redacted'] as num?)?.toInt() ?? 0,
    checks: parseChecks(r['guide']),
  );
}

/// The AI Intake and the deterministic guide (revision §23). The server decides; the app shows.
class IntakeRepository {
  IntakeRepository(this._api);
  final ApiService _api;

  Future<AssistResult> assistTicket(String text, Map<String, Object?> draft) async => parseAssist(await _api
      .json((c) => _api.intake(c).assistTicketWithHttpInfo(api.AssistIn(text: text, draft: draft))));

  /// A nameplate photo: the server reads it (§24.6); the device only captured it.
  Future<AssistResult> assistAssetPhoto(PickedPhoto photo, Map<String, Object?> draft) async {
    final file = http.MultipartFile.fromBytes('file', photo.bytes, filename: photo.name,
        contentType: MediaType.parse(photo.mimeType));
    return parseAssist(await _api.json((c) => _api.intake(c).assistFromFileWithHttpInfo('asset', file,
        draft: jsonEncode(draft))));
  }

  Future<List<GuideCheck>> guideTicket(Map<String, Object?> draft) async =>
      parseChecks(await _api.json((c) => _api.intake(c).guideTicketWithHttpInfo(api.GuideIn(draft: draft))));

  Future<List<GuideCheck>> guideAsset(Map<String, Object?> draft) async =>
      parseChecks(await _api.json((c) => _api.intake(c).guideAssetWithHttpInfo(api.GuideIn(draft: draft))));

  /// After the save: which suggestions the person kept (§23.11). Failing to record it loses
  /// nothing the person did, so a failure is swallowed.
  Future<void> recordOutcome(String runId, String recordUid, Map<String, Object?> finalValues) async {
    try {
      await _api.json((c) => _api.intake(c).recordOutcomeWithHttpInfo(
          runId, api.OutcomeIn(recordUid: recordUid, final_: finalValues)));
    } on Problem {
      // the record exists; the outcome is statistics
    }
  }
}

class SchemaRepository {
  SchemaRepository(this._api);
  final ApiService _api;

  Future<List<Map<String, Object?>>> _all() async =>
      _list(await _api.json((c) => _api.schemas(c).listSchemasWithHttpInfo())).map(_map).toList();

  Future<List<TicketKind>> ticketKinds() async => (await _all())
      .where((s) => s['applies_to'] == 'tickets' && s['is_concrete'] != false)
      .map((s) => TicketKind(s['uid'].toString(), s['name'].toString()))
      .toList()
    ..sort((a, b) => a.name.compareTo(b.name));

  Future<List<EquipmentType>> objectTypes() async => (await _all())
      .where((s) => s['applies_to'] == 'objects' && s['is_concrete'] != false)
      .map((s) => EquipmentType(s['uid'].toString(), s['name'].toString()))
      .toList()
    ..sort((a, b) => a.name.compareTo(b.name));

  Future<List<EquipmentType>> documentTypes() async => (await _all())
      .where((s) => s['applies_to'] == 'documents' && s['is_concrete'] != false)
      .map((s) => EquipmentType(s['uid'].toString(), s['name'].toString()))
      .toList()
    ..sort((a, b) => a.name.compareTo(b.name));

  /// The hierarchy of one kind of type: 'objects', 'tickets' or 'documents'.
  Future<TypeTree> tree(String appliesTo) async => TypeTree([
        for (final s in await _all())
          if (s['applies_to'] == appliesTo)
            TypeNode(
              uid: s['uid'].toString(),
              name: (s['name'] ?? '').toString(),
              parentUid: s['parent_schema_uid']?.toString(),
              concrete: s['is_concrete'] != false,
            ),
      ]);

  /// A type's attributes, with its ancestors' folded in (a child's own definition wins on the same
  /// key) — the same rule webapp/src/lib/schemaAttributes.ts effectiveAttributes() applies, so a
  /// record edited here sees the fields the web form would show.
  Future<List<AttributeDef>> effectiveAttributes(String schemaUid) async {
    final all = await _all();
    final byUid = {for (final s in all) s['uid'].toString(): s};
    final chain = <Map<String, Object?>>[];
    final seen = <String>{};
    Map<String, Object?>? current = byUid[schemaUid];
    while (current != null && seen.add(current['uid'].toString())) {
      chain.add(current);
      final parent = current['parent_schema_uid']?.toString();
      current = parent == null ? null : byUid[parent];
    }
    final merged = <String, AttributeDef>{};
    for (final s in chain.reversed) {
      for (final raw in _list(s['attributes']).map(_map)) {
        final def = _attributeDef(raw);
        if (def != null) merged[def.key] = def;
      }
    }
    return merged.values.toList();
  }

  /// [schemaUid] and every type beneath it in the tree — the same set a reference attribute with
  /// includeChildren set accepts (webapp/src/lib/schemaAttributes.ts descendantSchemaUids).
  Future<Set<String>> descendantSchemaUids(String schemaUid) async {
    final all = await _all();
    final children = <String, List<String>>{};
    for (final s in all) {
      final parent = s['parent_schema_uid']?.toString();
      if (parent != null) children.putIfAbsent(parent, () => []).add(s['uid'].toString());
    }
    final out = <String>{};
    final queue = [schemaUid];
    while (queue.isNotEmpty) {
      final uid = queue.removeLast();
      if (out.add(uid)) queue.addAll(children[uid] ?? const []);
    }
    return out;
  }

  AttributeDef? _attributeDef(Map<String, Object?> m) {
    final key = (m['key'] ?? m['name'])?.toString();
    if (key == null || key.isEmpty) return null;
    return AttributeDef(
      key: key,
      name: (m['name'] ?? key).toString(),
      type: (m['type'] ?? 'string').toString(),
      required: m['required'] == true,
      multiValue: m['multiValue'] == true || m['multi_value'] == true,
      minCardinality: (m['minCardinality'] ?? m['min_cardinality']) as int?,
      maxCardinality: (m['maxCardinality'] ?? m['max_cardinality']) as int?,
      options: _list(m['options']).map(_map).map((o) => (id: (o['id'] ?? '').toString(), value: (o['value'] ?? o['id'] ?? '').toString())).toList(),
      regex: m['regex']?.toString(),
      readOnly: m['readOnly'] == true || m['read_only'] == true,
      description: m['description']?.toString(),
      referenceSchemaUid: (m['referenceSchemaUid'] ?? m['reference_schema_uid'])?.toString(),
      includeChildren: m['includeChildren'] == true || m['include_children'] == true,
    );
  }
}

/// Files, sent in pieces with their hash so a weak network can resume (§5.5).
class UploadRepository {
  UploadRepository(this._api, {this.pieceSize = 1024 * 1024});
  final ApiService _api;
  final int pieceSize;

  /// Upload, verify and attach. [key] is the command's own key: each step derives its key from it,
  /// so a retry of the whole command resumes rather than duplicates.
  Future<String> uploadAndAttach(PickedPhoto photo,
      {String? ticketUid, String? assetUid, String? documentUid, String? revisionUid, required String key}) async {
    final digest = sha256.convert(photo.bytes).toString();
    final created = _map(await _api.json(
        (c) => _api.uploads(c).createUploadWithHttpInfo(api.UploadIn(
            filename: photo.name, contentType: photo.mimeType, size: photo.bytes.length, sha256: digest)),
        idempotencyKey: '$key:create'));
    final uid = created['uid'].toString();
    var offset = (created['offset'] as num?)?.toInt() ?? 0;
    while (offset < photo.bytes.length) {
      final end = (offset + pieceSize).clamp(0, photo.bytes.length);
      try {
        final r = _map(await _api.putBytes('/v1/uploads/$uid', {'offset': '$offset'}, photo.bytes.sublist(offset, end)));
        offset = (r['offset'] as num).toInt();
      } on Problem catch (p) {
        // Another attempt got further: resume where the server is.
        final at = p.current?['offset'];
        if (p.code == ProblemCode.conflict && at is num) {
          offset = at.toInt();
        } else {
          rethrow;
        }
      }
    }
    await _api.json((c) => _api.uploads(c).completeUploadWithHttpInfo(uid), idempotencyKey: '$key:complete');
    final attached = _map(await _api.json(
        (c) => ticketUid != null
            ? _api.uploads(c).attachToTicketWithHttpInfo(uid, ticketUid)
            : documentUid != null
                ? _api.uploads(c).attachToDocumentWithHttpInfo(uid, documentUid, revisionUid!)
                : _api.uploads(c).attachToAssetWithHttpInfo(uid, assetUid!),
        idempotencyKey: '$key:attach'));
    return (attached['attachment_uid'] ?? uid).toString();
  }
}

/// Changing tickets: every command carries its own idempotency key, edits carry the version read.
class TicketCommands {
  TicketCommands(this._api);
  final ApiService _api;

  Future<String> create({
    required String uid,
    required String title,
    required String description,
    required String subjectUid,
    String? kindUid,
    Map<String, Object?> attributes = const {},
  }) async {
    final r = _map(await _api.json(
        (c) => _api.issues(c).createIssueWithHttpInfo(api.IssueCreate(
            uid: uid,
            title: title,
            description: description,
            assetUid: subjectUid,
            schemaUid: kindUid,
            attributes: attributes)),
        idempotencyKey: 'ticket:$uid'));
    return r['uid'].toString();
  }

  Future<List<Comment>> comments(String ticketUid) async =>
      _list(await _api.json((c) => _api.issues(c).listIssueCommentsWithHttpInfo(ticketUid)))
          .map(_map)
          .map((m) => Comment(
              uid: m['uid'].toString(),
              author: (m['author'] ?? '').toString(),
              body: (m['body'] ?? '').toString(),
              at: _date(m['created_at'])))
          .toList();

  Future<void> comment(String ticketUid, String commentUid, String body) async {
    await _api.json(
        (c) => _api.issues(c).createIssueCommentWithHttpInfo(
            ticketUid, api.IssueCommentCreate(uid: commentUid, body: body)),
        idempotencyKey: 'comment:$commentUid');
  }

  Future<List<AttachmentInfo>> attachments(String ticketUid) async =>
      _list(await _api.json((c) => _api.issues(c).listIssueAttachmentsWithHttpInfo(ticketUid)))
          .map(_map)
          .map((m) => AttachmentInfo(
              uid: m['uid'].toString(),
              filename: (m['filename'] ?? '').toString(),
              mimeType: m['mime_type']?.toString(),
              size: (m['file_size'] as num?)?.toInt()))
          .toList();

  Future<List<TransitionOption>> transitions(String ticketUid) async =>
      _list(_map(await _api.json((c) => _api.issues(c).listTransitionsWithHttpInfo(ticketUid)))['transitions'])
          .map(_map)
          .map((t) => TransitionOption(
              to: t['to'].toString(),
              name: (t['name'] ?? 'Move').toString(),
              toName: (t['to_name'] ?? t['to']).toString(),
              category: t['category']?.toString(),
              requires: _list(t['requires']).map((e) => e.toString()).toList()))
          .toList();

  Future<TransitionResult> transition(String ticketUid, String to,
      {required int version, required String key, String? comment, String? resolution}) async {
    final r = await _api.raw(
        (c) => _api.issues(c).transitionIssueWithHttpInfo(
            ticketUid, api.TransitionIn(to: to, comment: comment, resolution: resolution)),
        idempotencyKey: key,
        ifMatch: '"$version"');
    return TransitionResult(state: (_map(r.body)['state'] ?? '').toString(), proposed: r.status == 202);
  }
}

/// Registering Equipment the person has in front of them (§24.8: never from a name).
class EquipmentCommands {
  EquipmentCommands(this._api);
  final ApiService _api;

  Future<String> register({
    required String uid,
    required String typeUid,
    required String name,
    String? key,
    required Map<String, Object?> attributes,
  }) async {
    final r = _map(await _api.json(
        (c) => _api.assets(c).createAssetWithHttpInfo(api.AssetCreate(
            uid: uid, schemaUid: typeUid, name: name, key: key, attributes: attributes)),
        idempotencyKey: 'asset:$uid'));
    return r['uid'].toString();
  }
}

class NotificationRepository {
  NotificationRepository(this._api);
  final ApiService _api;

  Future<List<NotificationItem>> mine({bool unreadOnly = false}) async =>
      _list(await _api.json((c) => _api.notifications(c).myNotificationsWithHttpInfo(unread: unreadOnly)))
          .map(_map)
          .map((n) => NotificationItem(
              id: (n['id'] as num).toInt(),
              title: (n['title'] ?? '').toString(),
              issueUid: n['issue_uid']?.toString(),
              kind: n['kind']?.toString(),
              read: n['read'] == true,
              at: _date(n['created_at'])))
          .toList();

  Future<void> markRead(int id) async {
    await _api.json((c) => _api.notifications(c).markReadWithHttpInfo(id));
  }
}
