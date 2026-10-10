import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/providers.dart';
import '../../widgets/related_by_meaning.dart';
import '../shell/app_shell.dart';

/// The knowledge graph: start from a piece of equipment, a ticket or a document and walk what it is connected
/// to — by the relations people made, and by what the written knowledge says is about the same thing.
class GraphScreen extends ConsumerStatefulWidget {
  const GraphScreen({super.key});

  @override
  ConsumerState<GraphScreen> createState() => _GraphScreenState();
}

class _GraphScreenState extends ConsumerState<GraphScreen> {
  final _query = TextEditingController();
  String _q = '';

  @override
  void dispose() {
    _query.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final r = _q.length < 2 ? null : ref.watch(searchProvider(_q));
    return Scaffold(
      appBar: AppBar(leading: const ShellMenuButton(), title: const Text('Knowledge graph')),
      body: Column(children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
          child: TextField(
            key: const Key('graph-search'),
            controller: _query,
            decoration: const InputDecoration(
              prefixIcon: Icon(Icons.search),
              hintText: 'Equipment, ticket or document to start from',
              border: OutlineInputBorder(),
            ),
            onChanged: (v) => setState(() => _q = v.trim()),
          ),
        ),
        Expanded(
          child: r == null
              ? const _Hint()
              : r.when(
                  loading: () => const Center(child: CircularProgressIndicator()),
                  error: (e, _) => Center(child: Text('$e')),
                  data: (res) => res.isEmpty
                      ? const Center(child: Text('Nothing matches.'))
                      : ListView(children: [
                          for (final a in [...res.assets, ...res.tickets, ...res.documents])
                            ListTile(
                              key: Key('graph-start-${a.uid}'),
                              leading: Icon(kindIcon(a.kind)),
                              title: Text(a.title ?? a.uid),
                              subtitle: a.subtitle == null ? null : Text(a.subtitle!),
                              onTap: () => context.push('/graph/${a.kind.name}/${Uri.encodeComponent(a.uid)}'
                                  '?title=${Uri.encodeComponent(a.title ?? a.uid)}'),
                            ),
                        ]),
                ),
        ),
      ]),
    );
  }
}

class _Hint extends StatelessWidget {
  const _Hint();

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Icon(Icons.hub_outlined, size: 56, color: Theme.of(context).colorScheme.outline),
            const SizedBox(height: 12),
            const Text('Find equipment, a ticket or a document to see what it is connected to, and what is '
                'about the same thing by meaning. Tap a neighbour to walk on from there.',
                textAlign: TextAlign.center),
          ]),
        ),
      );
}
