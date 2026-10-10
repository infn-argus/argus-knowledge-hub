import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/providers.dart';
import '../../core/link_parser.dart';
import '../../core/problem.dart';
import '../../domain/models.dart' show inWorkspace;
import '../../widgets/common.dart';

/// Opens a link or a label through the server's resolver, then replaces itself with the record.
/// A record that does not exist and one this person may not see look the same (I-MOB-6).
class ResolveScreen extends ConsumerWidget {
  const ResolveScreen({super.key, required this.path});

  final String path;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    ref.listen(resolveProvider(path), (_, next) {
      final target = next.value;
      if (target != null) context.pushReplacement(target.route);
    });
    final r = ref.watch(resolveProvider(path));
    final label = Uri.decodeComponent(path.split('/').last);
    return Scaffold(
      appBar: AppBar(title: Text(label)),
      body: r.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        data: (_) => const Center(child: CircularProgressIndicator()),
        error: (e, _) => e is Problem && e.code == ProblemCode.ambiguous
            ? _Candidates(e)
            : Column(children: [
                // A web link no record carries: probably someone else's code (a manufacturer's), not opened.
                if (e is Problem && e.code == ProblemCode.notFound && foreignLinkHost(label) != null)
                  NoticeBar(
                    key: const Key('resolve-foreign-link'),
                    icon: Icons.link_off,
                    text: 'This code is a link to ${foreignLinkHost(label)}. No ARGUS record carries it as a label, '
                        'and it was not opened.',
                  ),
                Expanded(child: ProblemView(e, onRetry: () => ref.invalidate(resolveProvider(path)))),
                // An unknown label on a unit in hand: register it, never invent it from a name (I-MOB-6).
                if (e is Problem && e.code == ProblemCode.notFound && path.startsWith('/lookup/'))
                  SafeArea(
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: FilledButton.tonalIcon(
                        key: const Key('resolve-register'),
                        onPressed: () => context.pushReplacement('/register?label=${Uri.encodeComponent(label)}'),
                        icon: const Icon(Icons.add_box_outlined),
                        label: const Text('Register this unit'),
                      ),
                    ),
                  ),
              ]),
      ),
    );
  }
}

/// A label value held by more than one record: nothing is opened; the person picks the one in
/// front of them, comparing what the labels say (A67).
class _Candidates extends StatelessWidget {
  const _Candidates(this.problem);

  final Problem problem;

  @override
  Widget build(BuildContext context) => ListView(children: [
        NoticeBar(icon: Icons.call_split, text: problem.message),
        for (final c in problem.candidates)
          ListTile(
            key: Key('candidate-${c['uid']}'),
            leading: const Icon(Icons.memory),
            title: Text(c['name']?.toString() ?? c['key'].toString()),
            subtitle: Text([
              c['key'],
              c['type'],
              if (c['workspace_id'] != null) 'in ${c['workspace_id']}',
              ...((c['attributes'] as Map?) ?? const {}).entries.map((e) => '${e.key} ${e.value}'),
            ].whereType<Object>().join(' · ')),
            onTap: () => context.pushReplacement(inWorkspace('/asset/${c['uid']}', c['workspace_id']?.toString())),
          ),
      ]);
}
