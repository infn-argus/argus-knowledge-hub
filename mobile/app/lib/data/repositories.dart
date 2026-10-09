import 'package:argus_api/api.dart' as api;

import '../core/problem.dart';
import '../domain/capture.dart' show AssetLabelInfo, AttachmentInfo, Comment;
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

  /// A reference attribute's target, named rather than the bare uid it is stored as — the single-record
  /// equivalent of [listByType], for showing what a reference points at without fetching everything
  /// [detail] does (context, installations, tickets…) just to read a name.
  Future<RecordBrief> brief(String uid) async {
    final asset = await _api.call((c) => _api.assets(c).getAsset(uid));
    return RecordBrief(uid: asset.uid, key: asset.key, name: asset.name, type: asset.type, schemaUid: asset.schemaUid);
  }

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
      isGlobal: asset.isGlobal,
      inboundRelationUids: asset.inboundRelations,
      outboundRelationUids: asset.outboundRelations,
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

  Future<List<AssetLabelInfo>> labels(String assetUid) async =>
      _list(await _api.json((c) => _api.assetSubresources(c).listLabelsWithHttpInfo(assetUid)))
          .map(_map)
          .map((m) => AssetLabelInfo(
              uid: m['uid'].toString(),
              type: (m['type'] ?? '').toString(),
              value: (m['value'] ?? '').toString(),
              verified: m['verified'] == true))
          .toList();

  /// Puts a label on the record — written by a person in the field, so not yet verified.
  Future<void> addLabel(String assetUid, String labelUid, String type, String value) async {
    final now = DateTime.now().toUtc();
    await _api.json(
        (c) => _api.assetSubresources(c).createLabelsWithHttpInfo(
            assetUid,
            api.AssetLabelCreate(
                uid: labelUid, type: type, value: value.trim(), issuer: 'field', createdAt: now, updatedAt: now)),
        idempotencyKey: 'asset-label:$labelUid');
  }

  Future<void> removeLabel(String assetUid, String labelUid) async =>
      _api.json((c) => _api.labels(c).deleteLabelWithHttpInfo(assetUid, labelUid));

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
  /// the same optimistic-concurrency rule every other edit in the app follows (§3.3). [current]'s own
  /// isGlobal/avatar/relation-cache fields travel unchanged in the same request: the generated client
  /// serializes every field of AssetUpdate (null or empty where unset, never omitted), and the server
  /// takes the whole body as the record's display/caching state — leaving them out would clear them.
  Future<void> save(AssetDetail current, Map<String, Object?> attributes, {required String key}) async {
    await _api.json(
        (c) => _api.assets(c).updateAssetWithHttpInfo(current.uid, api.AssetUpdate(
            attributes: attributes,
            isGlobal: current.isGlobal,
            avatarIconUid: current.avatarIconUid,
            inboundRelations: current.inboundRelationUids,
            outboundRelations: current.outboundRelationUids)),
        idempotencyKey: 'asset-edit:$key', ifMatch: '"${current.version ?? 0}"');
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
      schemaUid: t.schemaUid,
    );
  }

  /// The workspace's tickets, or only the open ones assigned to the signed-in person ([mine]).
  Future<List<TicketListItem>> list({bool mine = false}) async =>
      _list(await _api.json((c) => _api.issues(c).listIssuesWithHttpInfo(mine: mine)))
          .map(_map)
          .where((m) => m['deleted_at'] == null)
          .map((m) => TicketListItem(
                uid: m['uid'].toString(),
                title: (m['title'] ?? '').toString(),
                state: (m['state'] ?? '').toString(),
                priority: m['priority']?.toString(),
                assignee: m['assignee']?.toString(),
                assetUid: m['asset_uid']?.toString(),
                updatedAt: _date(m['updated_at']),
                createdAt: _date(m['created_at']),
                schemaUid: m['schema_uid']?.toString(),
                closed: m['closed_at'] != null,
              ))
          .toList()
        ..sort((a, b) => (b.updatedAt ?? DateTime(0)).compareTo(a.updatedAt ?? DateTime(0)));

  /// The priorities tickets can have, in the order the workspace defines them (its "priority" global value).
  Future<List<String>> priorities() async {
    final rows = _list(await _api.json((c) => _api.globalValues(c).listGlobalValuesWithHttpInfo(appliesTo: 'tickets')));
    final priority = rows.map(_map).where((g) => g['key'] == 'priority').firstOrNull;
    return _list(priority?['options']).map(_map).map((o) => (o['value'] ?? o['label'] ?? o['id']).toString()).toList();
  }

  /// Changes a ticket. Only the fields in [changes] are sent — not the generated model, which writes every
  /// field (null where unset) and would so clear the ones not being changed (the affected record, the
  /// assignee…). The version read must still be current (If-Match), as with every other edit (§3.3).
  Future<void> update(String uid, Map<String, Object?> changes, {required int version, required String key}) async {
    await _api.json((c) => c.invokeAPI('/v1/issues/$uid', 'PUT', [], changes, {}, {}, 'application/json'),
        idempotencyKey: 'ticket-edit:$key', ifMatch: '"$version"');
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
      documentTypeUid: d.documentTypeUid,
      steps: _list(rev?.steps).map((s) => (_map(s)['title'] ?? _map(s)['text'] ?? s).toString()).toList(),
    );
  }

  /// The files of one revision: the figures and attachments it was written, or approved, with.
  Future<List<AttachmentInfo>> revisionAttachments(String uid, String revUid) async =>
      _list(await _api.json((c) => _api.documents(c).listRevisionAttachmentsWithHttpInfo(uid, revUid)))
          .map(_map)
          .map((m) => AttachmentInfo(
              uid: m['uid'].toString(),
              filename: (m['filename'] ?? '').toString(),
              mimeType: m['mime_type']?.toString(),
              size: (m['file_size'] as num?)?.toInt()))
          .toList();

  Future<List<DocumentListItem>> list() async =>
      _list(await _api.json((c) => _api.documents(c).listDocumentsWithHttpInfo()))
          .map(_map)
          .map((m) => DocumentListItem(
                uid: m['uid'].toString(),
                code: (m['code'] ?? '').toString(),
                title: (m['title'] ?? '').toString(),
                published: m['current_revision_uid'] != null,
                documentTypeUid: m['document_type_uid']?.toString(),
                updatedAt: _date(m['updated_at']),
                createdAt: _date(m['created_at']),
                retired: m['retired_at'] != null,
                shared: m['is_global'] == true,
                workspaceId: m['workspace_id']?.toString(),
              ))
          .toList()
        ..sort((a, b) => (b.updatedAt ?? DateTime(0)).compareTo(a.updatedAt ?? DateTime(0)));

  /// Writes a new document; its text becomes the first revision, a draft. [assetUid], when given, is the
  /// record it describes — the same relation the web's "Write a document" from an asset makes.
  Future<String> create({
    required String uid,
    required String title,
    String? documentTypeUid,
    String? body,
    String? assetUid,
  }) async {
    final created = _map(await _api.json(
        (c) => c.invokeAPI('/v1/documents', 'POST', [], {
              'uid': uid,
              'title': title,
              'document_type_uid': ?documentTypeUid,
              if (body != null && body.isNotEmpty) 'body_markdown': body,
            }, {}, {}, 'application/json'),
        idempotencyKey: 'document:$uid'));
    if (assetUid != null) {
      await _api.json(
          (c) => _api.documents(c).createRelationWithHttpInfo(
              uid, api.DocumentRelationCreate(toType: api.DocumentRelationCreateToTypeEnum.asset, toUid: assetUid, relationType: 'describes')),
          idempotencyKey: 'document:$uid:describes:$assetUid');
    }
    return created['uid'].toString();
  }

  Future<List<DocumentRevision>> revisions(String uid) async =>
      _list(await _api.json((c) => _api.documents(c).listRevisionsWithHttpInfo(uid)))
          .map(_map)
          .map((m) => DocumentRevision(
                uid: m['uid'].toString(),
                number: (m['revision_number'] as num?)?.toInt() ?? 0,
                state: (m['state'] ?? '').toString(),
                body: m['body_markdown']?.toString(),
                authoredBy: m['authored_by']?.toString(),
                approvedBy: m['approved_by']?.toString(),
                reviewComment: m['review_comment']?.toString(),
                updatedAt: _date(m['updated_at']),
              ))
          .toList()
        ..sort((a, b) => b.number.compareTo(a.number));

  /// A new draft revision, starting from the text of [from] (the published one, typically).
  Future<void> newRevision(String uid, DocumentRevision? from) async {
    await _api.json(
        (c) => c.invokeAPI('/v1/documents/$uid/revisions', 'POST', [], {'body_markdown': from?.body ?? ''}, {}, {},
            'application/json'),
        idempotencyKey: 'document:$uid:revision:${from?.uid ?? 'new'}');
  }

  /// Changes a draft's text — only what is given, so its dates and steps stay as they are.
  Future<void> updateDraft(String uid, String revUid, {required String body}) async {
    await _api.json((c) => c.invokeAPI(
        '/v1/documents/$uid/revisions/$revUid', 'PUT', [], {'body_markdown': body}, {}, {}, 'application/json'));
  }

  Future<void> submit(String uid, String revUid) =>
      _api.json((c) => _api.documents(c).submitRevisionWithHttpInfo(uid, revUid));

  Future<void> approve(String uid, String revUid) =>
      _api.json((c) => _api.documents(c).approveRevisionWithHttpInfo(uid, revUid, api.ApproveAction()));

  Future<void> publish(String uid, String revUid) =>
      _api.json((c) => _api.documents(c).publishRevisionWithHttpInfo(uid, revUid));
}

class CockpitRepository {
  CockpitRepository(this._api);
  final ApiService _api;

  Future<Cockpit> overview() async {
    final o = _map(await _api.json((c) => _api.hub(c).overviewWithHttpInfo()));
    final tickets = o['tickets'] is Map ? _map(o['tickets']) : null;
    final documents = o['documents'] is Map ? _map(o['documents']) : null;
    final assets = o['assets'] is Map ? _map(o['assets']) : null;
    CockpitItem ticket(Map<String, Object?> t) => CockpitItem(
        kind: RecordKind.ticket,
        uid: t['uid'].toString(),
        label: (t['title'] ?? '').toString(),
        sub: [t['state'], t['priority']].whereType<Object>().join(' · '),
        at: _date(t['updated_at']));
    CockpitItem document(Map<String, Object?> d) => CockpitItem(
        kind: RecordKind.document,
        uid: d['uid'].toString(),
        label: '${d['code'] ?? ''} · ${d['title'] ?? ''}',
        sub: d['state']?.toString(),
        at: _date(d['updated_at']));
    CockpitItem asset(Map<String, Object?> a) => CockpitItem(
        kind: RecordKind.asset,
        uid: a['uid'].toString(),
        label: (a['name'] ?? a['key'] ?? '').toString(),
        sub: [a['key'], a['type']].whereType<Object>().join(' · '),
        at: _date(a['updated_at']),
        count: (a['open_tickets'] as num?)?.toInt());
    final recent = [
      ..._list(assets?['recent']).map(_map).map(asset),
      ..._list(tickets?['recent']).map(_map).map(ticket),
      ..._list(documents?['recent']).map(_map).map(document),
    ]..sort((a, b) => (b.at ?? DateTime(0)).compareTo(a.at ?? DateTime(0)));
    return Cockpit(
      mine: _list(tickets?['mine']).map(_map).map(ticket).toList(),
      openTickets: (tickets?['open'] as num?)?.toInt(),
      byState: _map(tickets?['by_state']).map((k, v) => MapEntry(k, (v as num?)?.toInt() ?? 0)),
      hotspots: _list(tickets?['hotspots']).map(_map).map(asset).toList(),
      awaitingReview: _list(documents?['awaiting_review']).map(_map).map(document).toList(),
      reviewOverdue: _list(documents?['review_overdue']).map(_map).map(document).toList(),
      recent: recent.take(12).toList(),
      totalTickets: (tickets?['total'] as num?)?.toInt(),
      unassigned: (tickets?['unassigned'] as num?)?.toInt(),
      withoutAsset: (tickets?['without_asset'] as num?)?.toInt(),
      inReview: (documents?['in_review'] as num?)?.toInt(),
      notLinked: (documents?['not_linked_to_assets'] as num?)?.toInt(),
      assets: (assets?['own'] as num?)?.toInt(),
    );
  }
}
