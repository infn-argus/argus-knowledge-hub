import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/providers.dart';
import '../../core/problem.dart';
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
            : ProblemView(e, onRetry: () => ref.invalidate(resolveProvider(path))),
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
            title: Text('${c['key']} · ${c['name']}'),
            subtitle: Text([
              c['type'],
              ...((c['attributes'] as Map?) ?? const {}).entries.map((e) => '${e.key} ${e.value}'),
            ].whereType<Object>().join(' · ')),
            onTap: () => context.pushReplacement('/asset/${c['uid']}'),
          ),
      ]);
}
