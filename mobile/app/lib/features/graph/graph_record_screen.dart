import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/providers.dart';
import '../../domain/models.dart';
import '../../widgets/common.dart';
import '../../widgets/related_by_meaning.dart';
import '../records/relation_graph_screen.dart';

/// One record in the knowledge graph: what it is connected to by the relations people made, and what its
/// written knowledge says is about the same thing. Every neighbour opens here in turn, to walk on.
class GraphRecordScreen extends ConsumerWidget {
  const GraphRecordScreen({super.key, required this.kind, required this.uid, required this.title});

  final RecordKind kind;
  final String uid;
  final String title;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final connected = ref.watch(connectedProvider((kind, uid)));
    String walk(LinkTarget t) =>
        '/graph/${t.kind.name}/${Uri.encodeComponent(t.uid)}?title=${Uri.encodeComponent(t.title ?? t.uid)}';
    return Scaffold(
      appBar: AppBar(title: Text(title, maxLines: 1, overflow: TextOverflow.ellipsis), actions: [
        IconButton(
          key: const Key('graph-open-record'),
          tooltip: 'Open the record',
          icon: const Icon(Icons.open_in_new),
          onPressed: () => context.push(LinkTarget(kind: kind, uid: uid).route),
        ),
      ]),
      body: ListView(key: const Key('graph-record'), children: [
        if (kind == RecordKind.asset)
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
            child: OutlinedButton.icon(
              key: const Key('graph-draw'),
              onPressed: () => Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => RelationGraphScreen(rootUid: uid, rootName: title))),
              icon: const Icon(Icons.hub_outlined),
              label: const Text('Draw its relations'),
            ),
          ),
        const SectionHeader('Connected'),
        connected.when(
          loading: () => const Padding(padding: EdgeInsets.all(16), child: LinearProgressIndicator()),
          error: (e, _) => ProblemView(e, onRetry: () => ref.invalidate(connectedProvider((kind, uid)))),
          data: (links) => links.isEmpty
              ? const ListTile(title: Text('Nothing is linked to it.'))
              : Column(children: [
                  for (final l in links)
                    ListTile(
                      key: Key('connected-${l.target.uid}'),
                      leading: Icon(kindIcon(l.target.kind)),
                      title: Text(l.target.title ?? l.target.uid, maxLines: 2, overflow: TextOverflow.ellipsis),
                      subtitle: Text([l.relation, ?l.target.subtitle].join(' · ')),
                      trailing: const Icon(Icons.chevron_right),
                      onTap: l.target.title == 'Restricted record' ? null : () => context.push(walk(l.target)),
                    ),
                ]),
        ),
        RelatedByMeaning(kind: kind, uid: uid, initiallyOpen: true),
      ]),
    );
  }
}
