import '../domain/models.dart';
import 'api_service.dart';

Map<String, Object?> _map(Object? o) => o is Map ? o.map((k, v) => MapEntry(k.toString(), v)) : const {};
List<Object?> _list(Object? o) => o is List ? o : const [];

RecordKind _kind(String k) => switch (k) {
      'ticket' => RecordKind.ticket,
      'document' => RecordKind.document,
      _ => RecordKind.asset,
    };

/// A record next to another: by a relation someone made (the knowledge graph), or by what its written
/// knowledge says (the semantic graph, from the knowledge index).
class GraphLink {
  const GraphLink({required this.target, required this.relation, this.score, this.excerpt, this.matched});

  final LinkTarget target;
  final String relation; // the relation's name, or 'similar'
  final double? score; // by meaning: how close, 0 to 1
  final String? excerpt; // by meaning: the other record's closest passage
  final String? matched; // by meaning: this record's
}

class SemanticNeighbours {
  const SemanticNeighbours({this.available = true, this.reason, this.basis, this.links = const []});

  final bool available;
  final String? reason;
  final String? basis; // 'passages' | 'description' | 'nothing indexed'
  final List<GraphLink> links;
}

class GraphRepository {
  GraphRepository(this._api);
  final ApiService _api;

  static String _kindParam(RecordKind k) => switch (k) {
        RecordKind.ticket => 'ticket',
        RecordKind.document => 'document',
        _ => 'asset',
      };

  /// What one record is connected to, one hop out: equipment, tickets, documents, people.
  Future<List<GraphLink>> connected(RecordKind kind, String uid) async {
    final g = _map(await _api.json((c) => _api.graph(c).getGraphWithHttpInfo(_kindParam(kind), uid, depth: 1)));
    final nodes = {
      for (final n in _list(g['nodes']).map(_map)) '${n['kind']}:${n['uid']}': n,
    };
    final self = '${_kindParam(kind)}:$uid';
    final out = <GraphLink>[];
    for (final e in _list(g['edges']).map(_map)) {
      final from = '${e['from_kind']}:${e['from_uid']}', to = '${e['to_kind']}:${e['to_uid']}';
      final other = from == self ? to : (to == self ? from : null);
      final n = other == null ? null : nodes[other];
      if (n == null || !const {'asset', 'ticket', 'document'}.contains(n['kind'])) continue;
      out.add(GraphLink(
        relation: (e['relation'] ?? '').toString(),
        target: LinkTarget(
            kind: _kind(n['kind'].toString()),
            uid: n['uid'].toString(),
            title: n['restricted'] == true ? 'Restricted record' : (n['label'] ?? '').toString(),
            subtitle: (n['sublabel'] ?? n['type_name'])?.toString()),
      ));
    }
    return out;
  }

  Future<SemanticNeighbours> byMeaning(RecordKind kind, String uid) async {
    final g = _map(await _api.json((c) => _api.graph(c).getSemanticGraphWithHttpInfo(_kindParam(kind), uid)));
    final nodes = {for (final n in _list(g['nodes']).map(_map)) '${n['kind']}:${n['uid']}': n};
    return SemanticNeighbours(
      available: g['available'] != false,
      reason: g['reason']?.toString(),
      basis: g['basis']?.toString(),
      links: [
        for (final e in _list(g['edges']).map(_map))
          GraphLink(
            relation: 'similar',
            score: (e['score'] as num?)?.toDouble(),
            excerpt: e['excerpt']?.toString(),
            matched: e['matched']?.toString(),
            target: LinkTarget(
              kind: _kind(e['to_kind'].toString()),
              uid: e['to_uid'].toString(),
              title: (nodes['${e['to_kind']}:${e['to_uid']}']?['label'] ?? e['to_uid']).toString(),
              subtitle: nodes['${e['to_kind']}:${e['to_uid']}']?['sublabel']?.toString(),
            ),
          ),
      ],
    );
  }
}
