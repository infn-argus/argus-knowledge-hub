import 'package:argus_api/api.dart' as api;

import '../core/problem.dart';
import '../domain/capture.dart' show AttachmentInfo, Comment;
import '../domain/models.dart';
import 'api_service.dart';

Map<String, Object?> _map(Object? o) => o is Map ? o.map((k, v) => MapEntry(k.toString(), v)) : const {};
DateTime? _date(Object? o) => o is String ? DateTime.tryParse(o) : null;
List<Object?> _list(Object? o) => o is List ? o : const [];

RecordBrief? _brief(Object? o) {
  if (o is! Map) return null;
  final m = _map(o);
  return RecordBrief(
    uid: m['uid']?.toString(),
    key: m['key']?.toString(),
    name: m['name']?.toString(),
    type: m['type']?.toString(),
    restricted: m['restricted'] == true,
  );
}

RecordKind _kind(String? k) => switch (k) {
      'position' => RecordKind.position,
      'installation' => RecordKind.installation,
      'document' => RecordKind.document,
      'ticket' => RecordKind.ticket,
      'review' => RecordKind.review,
      _ => RecordKind.asset,
    };

/// Workspaces the signed-in person may use.
class WorkspaceRepository {
  WorkspaceRepository(this._api);
  final ApiService _api;

  Future<List<WorkspaceChoice>> mine() async {
    final rows = await _api.call((c) => _api.workspaces(c).listMyWorkspaces());
    return rows
        .where((w) => w.canRead)
        .map((w) => WorkspaceChoice(id: w.id, name: w.name, canCreate: w.canCreate, canReadTickets: w.canReadTickets))
        .toList();
  }

  Future<String?> whoAmI() async {
    final me = await _api.call((c) => _api.workspaces(c).getMe());
    return me.name ?? me.email ?? me.workspaceId;
  }
}

/// The device this app runs on, as ARGUS knows it (revision §24.3).
class DeviceRepository {
  DeviceRepository(this._api);
  final ApiService _api;

  Future<String> register(String installationId, String appVersion) async {
    final d = _map(await _api.json((c) => _api.field(c).registerDeviceWithHttpInfo(
        api.DeviceIn(installationId: installationId, platform: _api.platform, appVersion: appVersion))));
    return d['id'].toString();
  }
}

/// Links, labels and searches: where they lead.
class LookupRepository {
  LookupRepository(this._api);
  final ApiService _api;

  Future<LinkTarget> resolveLink(String path) async {
    final r = _map(await _api.json((c) => _api.field(c).resolveLinkWithHttpInfo(path)));
    return LinkTarget(
      kind: _kind(r['kind']?.toString()),
      uid: r['uid'].toString(),
      title: (r['name'] ?? r['key'])?.toString(),
      subtitle: r['type']?.toString(),
      recordUid: (r['record_uid'] ?? r['position_uid'])?.toString(),
    );
  }

  /// A label value (a key, an inventory number, an old Jira or Insight identifier).
  Future<LinkTarget> lookup(String identifier) => resolveLink('/lookup/${Uri.encodeComponent(identifier)}');

  Future<SearchResults> search(String q) async {
    final r = _map(await _api.json((c) => _api.hub(c).searchWithHttpInfo(q, limit: 10)));
    return SearchResults(
      assets: _list(r['assets']).map(_map).map((a) => LinkTarget(
            kind: RecordKind.asset,
            uid: a['uid'].toString(),
            title: '${a['key']} · ${a['name']}',
            subtitle: a['type']?.toString(),
          )).toList(),
      tickets: _list(r['tickets']).map(_map).map((t) => LinkTarget(
            kind: RecordKind.ticket,
            uid: t['uid'].toString(),
            title: t['title']?.toString(),
            subtitle: t['state']?.toString(),
          )).toList(),
      documents: _list(r['documents']).map(_map).map((d) => LinkTarget(
            kind: RecordKind.document,
            uid: d['uid'].toString(),
            title: '${d['code']} · ${d['title']}',
            subtitle: d['state']?.toString(),
          )).toList(),
    );
  }
}

/// Equipment and Positions, with what is installed and what concerns them.
class AssetRepository {
  AssetRepository(this._api);
  final ApiService _api;

  Future<AssetDetail> detail(String uid) async {
    final asset = await _api.call((c) => _api.assets(c).getAsset(uid));
    final context = _map(await _api.json((c) => _api.hub(c).assetContextWithHttpInfo(uid)));
    final typePath = _list(context['type_path']).map((e) => e.toString()).toList();
    final isPosition = context['nature'] == 'position';
    List<InstallationInfo> installations = const [];
    try {
      final rows = await _api.json((c) => isPosition
          ? _api.installations(c).listInstallationsWithHttpInfo(positionUid: uid)
          : _api.installations(c).listInstallationsWithHttpInfo(assetUid: uid));
      installations = _list(rows).map(_map).map((i) => InstallationInfo(
            uid: i['uid'].toString(),
            status: (i['status'] ?? 'Proposed').toString(),
            temporalState: (i['temporal_state'] ?? 'Planned').toString(),
            certainty: i['temporal_certainty']?.toString(),
            position: _brief(i['position']),
            asset: _brief(i['asset']),
            from: When.fromJson(i['valid_from']),
            until: When.fromJson(i['valid_until']),
          )).toList();
    } on Problem catch (p) {
      if (p.code != ProblemCode.notFound && p.code != ProblemCode.forbidden) rethrow;
    }
    final relationItems = _list(_map(context['relations'])['items']).map(_map).map((r) => RelationItem(
          uid: r['uid'].toString(),
          key: (r['key'] ?? '').toString(),
          name: (r['name'] ?? r['key'] ?? '').toString(),
          type: (r['type'] ?? '').toString(),
          relation: (r['relation'] ?? '').toString(),
          direction: (r['direction'] ?? 'out').toString(),
        )).toList();
    return AssetDetail(
      uid: asset.uid,
      key: asset.key,
      name: asset.name,
      type: asset.type,
      typePath: typePath,
      recordStatus: asset.recordStatus,
      attributes: _map(asset.attributes),
      isPosition: isPosition,
      installations: installations,
      relations: relationItems,
      processing: context['processing'] != null,
      restricted: context['restricted']?.toString(),
      avatarIconUid: asset.avatarIconUid,
      version: asset.version,
      schemaUid: asset.schemaUid,
      tickets: _list(context['tickets']).map(_map).map((t) => TicketSummary(
            uid: t['uid'].toString(),
            title: (t['title'] ?? '').toString(),
            state: (t['state'] ?? '').toString(),
            priority: t['priority']?.toString(),
            open: t['open'] == true,
          )).toList(),
      documents: _list(context['documents']).map(_map).map((d) => DocumentSummary(
            uid: d['uid'].toString(),
            code: (d['code'] ?? '').toString(),
            title: (d['title'] ?? '').toString(),
            state: d['state']?.toString(),
            reviewOverdue: d['review_overdue'] == true,
          )).toList(),
    );
  }

  /// What is written on the record, next to the equipment: its comments, its recorded history, and its
  /// files. Three separate calls (like the ticket screen's), so one failing or refreshing does not block
  /// the others, and the field client's cache can keep each independently offline (I-MOB caching).

  Future<List<Comment>> comments(String assetUid) async =>
      _list(await _api.json((c) => _api.assetSubresources(c).listCommentsWithHttpInfo(assetUid)))
          .map(_map)
          .map((m) => Comment(
              uid: m['uid'].toString(),
              author: (m['author'] ?? '').toString(),
              body: (m['text'] ?? '').toString(),
              at: _date(m['created'])))
          .toList()
        ..sort((a, b) => (b.at ?? DateTime(0)).compareTo(a.at ?? DateTime(0)));

  /// A comment is a small piece of the asset's recorded history (asset-subresources are a generic,
  /// client-stamped log, not a live-authored thread like a ticket's): the person and the moment travel
  /// with the text, the same way the web app's "Add comment" form sends them.
  Future<void> comment(String assetUid, String commentUid, String author, String body) async {
    final now = DateTime.now().toUtc();
    await _api.json(
        (c) => _api.assetSubresources(c).createCommentsWithHttpInfo(
            assetUid, api.AssetCommentCreate(uid: commentUid, author: author, text: body, created: now, updated: now)),
        idempotencyKey: 'asset-comment:$commentUid');
  }

  Future<List<HistoryEntry>> history(String assetUid) async =>
      _list(await _api.json((c) => _api.assetSubresources(c).listHistoryWithHttpInfo(assetUid)))
          .map(_map)
          .map((m) => HistoryEntry(
              uid: m['uid'].toString(),
              type: (m['type'] ?? '').toString(),
              author: (m['author'] ?? '').toString(),
              details: (m['details'] ?? '').toString(),
              at: _date(m['timestamp'])))
          .toList()
        ..sort((a, b) => (b.at ?? DateTime(0)).compareTo(a.at ?? DateTime(0)));

  Future<List<AttachmentInfo>> attachments(String assetUid) async =>
      _list(await _api.json((c) => _api.attachments(c).listAttachmentsWithHttpInfo(assetUid: assetUid)))
          .map(_map)
          .map((m) => AttachmentInfo(
              uid: m['uid'].toString(),
              filename: (m['filename'] ?? '').toString(),
              mimeType: m['mime_type']?.toString(),
              size: (m['file_size'] as num?)?.toInt()))
          .toList();

  /// Candidates for a reference-attribute picker: every asset of [schemaUid] (unfiltered — the whole
  /// workspace's assets — when null, for the caller to narrow down to a reference's allowed descendant
  /// types itself, the same split the web form's ReferenceInput makes between a plain and an
  /// includeChildren reference).
  Future<List<RecordBrief>> listByType(String? schemaUid) async =>
      _list(await _api.json((c) => _api.assets(c).listAssetsWithHttpInfo(schemaUid: schemaUid)))
          .map(_map)
          .map((m) => RecordBrief(
              uid: m['uid']?.toString(),
              key: m['key']?.toString(),
              name: m['name']?.toString(),
              type: m['type']?.toString(),
              schemaUid: m['schema_uid']?.toString()))
          .toList();

  /// Saves the edited attributes. The version read with the record must still be current (If-Match),
  /// the same optimistic-concurrency rule every other edit in the app follows (§3.3).
  Future<void> save(String assetUid, Map<String, Object?> attributes, {required int version, required String key}) async {
    await _api.json(
        (c) => _api.assets(c).updateAssetWithHttpInfo(assetUid, api.AssetUpdate(attributes: attributes)),
        idempotencyKey: 'asset-edit:$key', ifMatch: '"$version"');
  }
}

class TicketRepository {
  TicketRepository(this._api);
  final ApiService _api;

  Future<TicketDetail> detail(String uid) async {
    final t = await _api.call((c) => _api.issues(c).getIssue(uid));
    return TicketDetail(
      uid: t.uid,
      title: t.title,
      state: t.state,
      description: t.description,
      priority: t.priority,
      assetUid: t.assetUid,
      occurredFrom: When.fromJson(_map(t.attributes)['occurred_from']),
      version: t.version,
      attributes: _map(t.attributes),
    );
  }
}

class DocumentRepository {
  DocumentRepository(this._api);
  final ApiService _api;

  Future<DocumentDetail> detail(String uid) async {
    final d = await _api.call((c) => _api.documents(c).getDocument(uid));
    api.DocumentRevisionOut? rev;
    try {
      rev = await _api.call((c) => _api.documents(c).getCurrentRevision(uid));
    } on Problem catch (p) {
      if (p.code != ProblemCode.notFound) rethrow;
    }
    return DocumentDetail(
      uid: d.uid,
      code: d.code,
      title: d.title,
      authorityLevel: d.authorityLevel,
      revisionState: rev?.state,
      revisionNumber: rev?.revisionNumber,
      body: rev?.bodyMarkdown,
      nextReviewDue: rev?.nextReviewDue,
      supersededBy: d.supersededByUid,
      steps: _list(rev?.steps).map((s) => (_map(s)['title'] ?? _map(s)['text'] ?? s).toString()).toList(),
    );
  }
}
