import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/providers.dart';
import '../../domain/models.dart';
import '../../widgets/common.dart';

/// Home: find a record by scanning its label or by typing (flutter-app-design §5.1).
class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  final _query = TextEditingController();
  Timer? _debounce;
  String _q = '';

  @override
  void dispose() {
    _debounce?.cancel();
    _query.dispose();
    super.dispose();
  }

  void _changed(String v) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 300), () => setState(() => _q = v.trim()));
  }

  void _submit(String v) {
    final text = v.trim();
    if (text.isEmpty) return;
    // Enter on a label value (a key, an inventory number, a Jira key) goes straight to lookup.
    context.push('/lookup/${Uri.encodeComponent(text)}');
  }

  @override
  Widget build(BuildContext context) {
    final session = ref.watch(sessionProvider).value;
    return Scaffold(
      appBar: AppBar(
        title: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('ARGUS Field'),
          if (session?.workspaceName != null)
            Text(session!.workspaceName!, style: Theme.of(context).textTheme.labelMedium),
        ]),
        actions: [
          PopupMenuButton<String>(
            key: const Key('home-menu'),
            onSelected: (v) {
              switch (v) {
                case 'workspace':
                  context.push('/workspace');
                case 'diagnostics':
                  context.push('/diagnostics');
                case 'signout':
                  ref.read(sessionProvider.notifier).signOut();
              }
            },
            itemBuilder: (_) => const [
              PopupMenuItem(value: 'workspace', child: Text('Switch workspace')),
              PopupMenuItem(value: 'diagnostics', child: Text('About and diagnostics')),
              PopupMenuItem(value: 'signout', child: Text('Sign out')),
            ],
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        key: const Key('home-scan'),
        onPressed: () => context.push('/scan'),
        icon: const Icon(Icons.qr_code_scanner),
        label: const Text('Scan label'),
      ),
      body: Column(children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
          child: TextField(
            key: const Key('home-search'),
            controller: _query,
            textInputAction: TextInputAction.search,
            decoration: InputDecoration(
              prefixIcon: const Icon(Icons.search),
              hintText: 'Key, name, serial, ticket or document',
              border: const OutlineInputBorder(),
              suffixIcon: _query.text.isEmpty
                  ? null
                  : IconButton(
                      icon: const Icon(Icons.clear),
                      onPressed: () {
                        _query.clear();
                        setState(() => _q = '');
                      }),
            ),
            onChanged: _changed,
            onSubmitted: _submit,
          ),
        ),
        Expanded(child: _q.length < 2 ? const _Hint() : _Results(q: _q)),
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
          child: Text(
            'Scan the label on the equipment or its position, or type at least two characters.\n'
            'Press Enter to look up an exact label value, such as an old Jira key.',
            textAlign: TextAlign.center,
            style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant),
          ),
        ),
      );
}

class _Results extends ConsumerWidget {
  const _Results({required this.q});

  final String q;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final r = ref.watch(searchProvider(q));
    return r.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => ProblemView(e, onRetry: () => ref.invalidate(searchProvider(q))),
      data: (res) => res.isEmpty
          ? Center(child: Text('Nothing matches "$q".'))
          : ListView(padding: const EdgeInsets.only(bottom: 96), children: [
              if (res.assets.isNotEmpty) ...[
                SectionHeader('Assets', trailing: '${res.assets.length}'),
                for (final t in res.assets) _hit(context, t, Icons.memory),
              ],
              if (res.tickets.isNotEmpty) ...[
                SectionHeader('Tickets', trailing: '${res.tickets.length}'),
                for (final t in res.tickets) _hit(context, t, Icons.confirmation_number_outlined),
              ],
              if (res.documents.isNotEmpty) ...[
                SectionHeader('Documents', trailing: '${res.documents.length}'),
                for (final t in res.documents) _hit(context, t, Icons.description_outlined),
              ],
            ]),
    );
  }

  Widget _hit(BuildContext context, LinkTarget t, IconData icon) => ListTile(
        leading: Icon(icon),
        title: Text(t.title ?? t.uid, maxLines: 2, overflow: TextOverflow.ellipsis),
        subtitle: t.subtitle == null ? null : Text(t.subtitle!),
        onTap: () => context.push(t.route),
      );
}
