import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app/providers.dart';
import '../records/relation_graph_screen.dart';
import '../shell/app_shell.dart';

/// The knowledge graph: start from a piece of equipment and walk what it is connected to — what it is part
/// of, what powers it, what it is installed in — as the web's graph does.
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
              hintText: 'Equipment to start from',
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
                  data: (res) => res.assets.isEmpty
                      ? const Center(child: Text('No equipment matches.'))
                      : ListView(children: [
                          for (final a in res.assets)
                            ListTile(
                              key: Key('graph-start-${a.uid}'),
                              leading: const Icon(Icons.hub_outlined),
                              title: Text(a.title ?? a.uid),
                              subtitle: a.subtitle == null ? null : Text(a.subtitle!),
                              onTap: () => Navigator.of(context, rootNavigator: true).push(MaterialPageRoute(
                                  builder: (_) => RelationGraphScreen(rootUid: a.uid, rootName: a.title ?? a.uid))),
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
            const Text('Find a piece of equipment to see what it is connected to: what it is part of, what '
                'powers it, where it is installed. Tap a neighbour to walk on from there.',
                textAlign: TextAlign.center),
          ]),
        ),
      );
}
