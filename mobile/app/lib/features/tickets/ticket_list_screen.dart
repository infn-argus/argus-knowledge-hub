import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/providers.dart';
import '../../core/problem.dart';
import '../../domain/models.dart';
import '../../widgets/common.dart';

enum _Show { open, mine, all }

/// The workspace's tickets: the open ones, the ones assigned to me, or all — searchable by title. A new
/// ticket is reported on the equipment it is about, so "New ticket" first asks for its label.
class TicketListScreen extends ConsumerStatefulWidget {
  const TicketListScreen({super.key});

  @override
  ConsumerState<TicketListScreen> createState() => _TicketListScreenState();
}

class _TicketListScreenState extends ConsumerState<TicketListScreen> {
  _Show _show = _Show.open;
  String _q = '';

  Future<void> _newTicket() async {
    final path = await context.push<String>('/scan?pick=1');
    if (path == null || !mounted) return;
    try {
      final target = await ref.read(lookupRepositoryProvider).resolveLink(path);
      if (!mounted) return;
      if (target.kind == RecordKind.ticket || target.kind == RecordKind.document || target.kind == RecordKind.review) {
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('That code is not on equipment or a position. Scan the one the ticket is about.')));
        return;
      }
      context.push('/report/${target.recordUid ?? target.uid}');
    } on Problem catch (p) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(p.message)));
    }
  }

  @override
  Widget build(BuildContext context) {
    final r = ref.watch(ticketListProvider(_show == _Show.mine));
    return Scaffold(
      appBar: AppBar(title: const Text('Tickets')),
      floatingActionButton: FloatingActionButton.extended(
        key: const Key('tickets-new'),
        onPressed: _newTicket,
        icon: const Icon(Icons.add),
        label: const Text('New ticket'),
      ),
      body: Column(children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
          child: SegmentedButton<_Show>(
            key: const Key('tickets-show'),
            segments: const [
              ButtonSegment(value: _Show.open, label: Text('Open')),
              ButtonSegment(value: _Show.mine, label: Text('Mine')),
              ButtonSegment(value: _Show.all, label: Text('All')),
            ],
            selected: {_show},
            onSelectionChanged: (s) => setState(() => _show = s.first),
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
          child: TextField(
            key: const Key('tickets-search'),
            decoration: const InputDecoration(prefixIcon: Icon(Icons.search), hintText: 'Search by title'),
            onChanged: (v) => setState(() => _q = v.trim().toLowerCase()),
          ),
        ),
        Expanded(
          child: r.when(
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (e, _) => ProblemView(e, onRetry: () => ref.invalidate(ticketListProvider(_show == _Show.mine))),
            data: (all) {
              final shown = all
                  .where((t) => _show == _Show.all || !t.closed)
                  .where((t) => _q.isEmpty || t.title.toLowerCase().contains(_q))
                  .toList();
              if (shown.isEmpty) {
                return Center(
                  child: Text(_show == _Show.mine ? 'No open tickets are assigned to you.' : 'No tickets match.'),
                );
              }
              return RefreshIndicator(
                onRefresh: () async => ref.invalidate(ticketListProvider(_show == _Show.mine)),
                child: ListView.separated(
                  key: const Key('tickets-list'),
                  padding: const EdgeInsets.only(bottom: 88),
                  itemCount: shown.length,
                  separatorBuilder: (_, _) => const Divider(height: 1),
                  itemBuilder: (context, i) => _TicketTile(shown[i]),
                ),
              );
            },
          ),
        ),
      ]),
    );
  }
}

class _TicketTile extends StatelessWidget {
  const _TicketTile(this.t);

  final TicketListItem t;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return ListTile(
      key: Key('ticket-${t.uid}'),
      leading: Icon(t.closed ? Icons.check_circle_outline : Icons.confirmation_number_outlined,
          color: t.closed ? theme.colorScheme.outline : theme.colorScheme.primary),
      title: Text(t.title, maxLines: 2, overflow: TextOverflow.ellipsis),
      subtitle: Text([
        t.state,
        if (t.priority != null) t.priority!,
        if (t.assignee != null) t.assignee!,
        if (t.updatedAt != null) 'updated ${formatWhenDate(t.updatedAt)}',
      ].join(' · ')),
      onTap: () => context.push('/ticket/${t.uid}'),
    );
  }
}
