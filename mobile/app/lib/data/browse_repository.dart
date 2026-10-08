import 'api_service.dart';

Map<String, Object?> _map(Object? o) => o is Map ? o.map((k, v) => MapEntry(k.toString(), v)) : const {};
DateTime? _date(Object? o) => o is String ? DateTime.tryParse(o) : null;
List<Object?> _list(Object? o) => o is List ? o : const [];

/// How a list is ordered: by name, or by when its records were created or last changed.
enum SortBy {
  name('Name', 'name'),
  created('Created', 'created'),
  updated('Updated', 'updated');

  const SortBy(this.label, this.param);
  final String label;
  final String param;
}

/// A list's order: what it is sorted by, and which way.
class ListOrder {
  const ListOrder(this.by, {this.descending = false});

  final SortBy by;
  final bool descending;

  /// Times newest first, names A to Z, unless the person turns it round.
  static const byUpdate = ListOrder(SortBy.updated, descending: true);

  ListOrder flipped() => ListOrder(by, descending: !descending);

  int compare<T>(T a, T b, {required String Function(T) name, DateTime? Function(T)? created,
      DateTime? Function(T)? updated}) {
    final int c = switch (by) {
      SortBy.name => name(a).toLowerCase().compareTo(name(b).toLowerCase()),
      SortBy.created => _time(created?.call(a)).compareTo(_time(created?.call(b))),
      SortBy.updated => _time(updated?.call(a)).compareTo(_time(updated?.call(b))),
    };
    return descending ? -c : c;
  }

  static DateTime _time(DateTime? t) => t ?? DateTime.fromMillisecondsSinceEpoch(0);

  @override
  bool operator ==(Object other) => other is ListOrder && other.by == by && other.descending == descending;

  @override
  int get hashCode => Object.hash(by, descending);
}

/// One row of the equipment list.
class AssetRow {
  const AssetRow({required this.uid, required this.key, required this.name, required this.type,
      this.schemaUid, this.createdAt, this.updatedAt, this.shared = false, this.status});

  final String uid;
  final String key;
  final String name;
  final String type;
  final String? schemaUid;
  final DateTime? createdAt;
  final DateTime? updatedAt;
  final bool shared;
  final String? status;
}

/// A page of the equipment list, and how many there are in all.
class AssetPage {
  const AssetPage(this.rows, this.total);
  final List<AssetRow> rows;
  final int total;
}

/// Browsing the workspace's equipment a page at a time — a workspace has thousands of records, which no
/// phone should download to show twenty.
class BrowseRepository {
  BrowseRepository(this._api);
  final ApiService _api;

  static const pageSize = 50;

  Future<AssetPage> assets({String? schemaUid, String q = '', ListOrder order = const ListOrder(SortBy.name),
      int offset = 0}) async {
    final r = await _api.raw((c) => _api.assets(c).listAssetsWithHttpInfo(
          schemaUid: schemaUid,
          includeSubtypes: schemaUid != null,
          q: q.trim().isEmpty ? null : q.trim(),
          sort: order.by.param,
          order: order.descending ? 'desc' : 'asc',
          limit: pageSize,
          offset: offset,
        ));
    final rows = [
      for (final m in _list(r.body).map(_map))
        AssetRow(
          uid: m['uid'].toString(),
          key: (m['key'] ?? '').toString(),
          name: (m['name'] ?? '').toString(),
          type: (m['type'] ?? '').toString(),
          schemaUid: m['schema_uid']?.toString(),
          createdAt: _date(m['created_at']),
          updatedAt: _date(m['updated_at']),
          shared: m['is_global'] == true,
          status: m['record_status']?.toString(),
        ),
    ];
    final total = int.tryParse(r.headers['x-total-count'] ?? '') ?? offset + rows.length;
    return AssetPage(rows, total);
  }

  /// Each equipment type's own number of records, for the type tree.
  Future<Map<String, int>> assetTypeCounts() async => {
        for (final e in _map(await _api.json((c) => _api.assets(c).assetTypeCountsWithHttpInfo())).entries)
          e.key: (e.value as num?)?.toInt() ?? 0,
      };
}
