import 'package:argus_api/api.dart' as api;

import '../domain/capture.dart';
import 'api_service.dart';
import 'capture_repositories.dart' show parseChecks;

Map<String, Object?> _map(Object? o) => o is Map ? o.map((k, v) => MapEntry(k.toString(), v)) : const {};
List<Object?> _list(Object? o) => o is List ? o : const [];

/// The guided replacement (flutter-app-design §8): a dry run, then one atomic command.
class ReplacementRepository {
  ReplacementRepository(this._api);
  final ApiService _api;

  api.ReplaceIn _body(ReplacementDraft d, {required bool dryRun}) => api.ReplaceIn(
        positionUid: d.positionUid,
        incomingUid: d.incomingUid!,
        outgoingUid: d.outgoingUid,
        seenInstallationUid: d.seenInstallationUid,
        at: d.at.toUtc(),
        precision: d.precision,
        reason: d.reason,
        condition: d.condition,
        workReference: d.workReference,
        evidence: d.evidence,
        dryRun: dryRun,
      );

  Future<ReplacementPreview> preview(ReplacementDraft d) async {
    final r = _map(await _api.json((c) => _api.installations(c).replaceWithHttpInfo(_body(d, dryRun: true))));
    final cons = _map(r['consequences']);
    final current = _map(r['current']);
    ({String uid, String title}) pair(Object? o) {
      final m = _map(o);
      return (uid: m['uid'].toString(), title: (m['title'] ?? m['code'] ?? '').toString());
    }

    return ReplacementPreview(
      outcome: (r['outcome'] ?? 'refused').toString(),
      reasons: _list(r['reasons']).map((e) => e.toString()).toList(),
      checks: parseChecks({'checks': r['checks']}),
      currentInstallationUid: current['installation_uid']?.toString(),
      currentUnit: BriefRecord.fromJson(current['unit']),
      incoming: BriefRecord.fromJson(r['incoming']),
      accessPoints: _list(cons['access_points']).map(BriefRecord.fromJson).whereType<BriefRecord>().toList(),
      segments: _list(cons['segments']).map(_map).map((s) => SegmentConsequence(
            name: (s['name'] ?? '').toString(),
            status: (s['status'] ?? '').toString(),
            safetyClass: (s['safety_class'] ?? 'none').toString(),
            reason: s['reason']?.toString(),
          )).toList(),
      hiddenSegments: (cons['hidden_segments'] as num?)?.toInt() ?? 0,
      documents: _list(cons['documents']).map(pair).toList(),
      openTickets: _list(cons['open_tickets']).map(pair).toList(),
    );
  }

  Future<ReplacementResult> submit(ReplacementDraft d) async {
    final r = await _api.raw((c) => _api.installations(c).replaceWithHttpInfo(_body(d, dryRun: false)),
        idempotencyKey: 'replace:${d.commandUid}');
    final b = _map(r.body);
    return ReplacementResult(
      applied: b['outcome'] == 'applied',
      reasons: _list(b['reasons']).map((e) => e.toString()).toList(),
      reviewItem: b['review_item']?.toString(),
      discrepancyItem: b['discrepancy_item']?.toString(),
    );
  }
}

/// What the person captured for a replacement, before it is sent.
class ReplacementDraft {
  ReplacementDraft({required this.commandUid, required this.positionUid, this.seenInstallationUid});

  final String commandUid; // one command, one key (§3.2)
  final String positionUid;
  final String? seenInstallationUid; // null: the Position was empty when the person looked
  String? outgoingUid;
  String? incomingUid;
  DateTime at = DateTime.now();
  String precision = 'instant';
  String reason = 'Failure';
  String? condition;
  String? workReference;
  Map<String, Object?>? evidence;
}

/// The review items routed to the person, one at a time, with the decisions allowed here.
class ReviewRepository {
  ReviewRepository(this._api);
  final ApiService _api;

  Future<List<ReviewItem>> mine() async {
    final r = _map(await _api.json((c) => api.LedgerApi(c).myReviewItemsWithHttpInfo()));
    return _list(r['items']).map(_map).map((i) => ReviewItem(
          key: i['key'].toString(),
          kind: (i['kind'] ?? '').toString(),
          queue: (i['queue'] ?? '').toString(),
          age: (i['age'] as num?)?.toInt() ?? 0,
          overdue: i['overdue'] == true,
          record: BriefRecord.fromJson(i['record']),
          detail: _map(i['detail']),
          decisions: _list(i['decisions']).map((e) => e.toString()).toList(),
        )).toList();
  }

  /// Apply one decision; [reason] and [value] as the decision needs them.
  Future<void> decide(ReviewItem item, String decision, {String? reason, Object? value}) async {
    final key = 'review:${item.key}:$decision';
    switch (item.kind) {
      case 'replacement_proposal' when decision == 'confirm':
        await _api.json((c) => api.LedgerApi(c).confirmReplacementWithHttpInfo(item.id), idempotencyKey: key);
      case 'replacement_proposal' || 'outgoing_discrepancy':
        await _api.json(
            (c) => api.LedgerApi(c).rejectReplacementWithHttpInfo(item.id, api.DecideReplacementIn(reason: reason)),
            idempotencyKey: key);
      case 'stale_command':
        await _api.json(
            (c) => api.LedgerApi(c).closeStaleCommandWithHttpInfo(
                item.id, api.CloseReviewIn(outcome: decision, reason: reason)),
            idempotencyKey: key);
      case 'ai_proposal':
        final claim = item.detail['claim_id'].toString();
        await _api.json(
            (c) => _api.intake(c).decideProposalWithHttpInfo(
                claim, api.DecideIn(action: decision, reason: reason, value: value)),
            idempotencyKey: key);
      default:
        throw UnsupportedError('${item.kind} is decided on the web');
    }
  }
}
