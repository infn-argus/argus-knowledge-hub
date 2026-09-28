import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/providers.dart';
import '../../widgets/common.dart';

class TicketScreen extends ConsumerWidget {
  const TicketScreen({super.key, required this.uid});

  final String uid;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final r = ref.watch(ticketDetailProvider(uid));
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Ticket')),
      body: r.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => ProblemView(e, onRetry: () => ref.invalidate(ticketDetailProvider(uid))),
        data: (t) => ListView(padding: const EdgeInsets.all(16), children: [
          Text(t.title, key: const Key('ticket-title'), style: theme.textTheme.headlineSmall),
          const SizedBox(height: 8),
          Wrap(spacing: 8, children: [
            StatusChip(t.state, tone: theme.colorScheme.primary),
            if (t.priority != null) StatusChip(t.priority!),
            if (t.occurredFrom?.nominal != null) StatusChip('occurred ${formatWhenDate(t.occurredFrom!.nominal)}'),
          ]),
          if (t.assetUid != null) ...[
            const SizedBox(height: 12),
            OutlinedButton.icon(
              onPressed: () => context.push('/asset/${t.assetUid}'),
              icon: const Icon(Icons.memory),
              label: const Text('Open the asset'),
            ),
          ],
          const SizedBox(height: 16),
          SelectableText((t.description ?? '').isEmpty ? 'No description.' : t.description!),
        ]),
      ),
    );
  }
}
