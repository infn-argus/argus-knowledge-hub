import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/providers.dart';
import '../../domain/models.dart';
import '../../widgets/common.dart';

/// The workspace's documents, searchable by title or code. One with nothing published yet is marked so —
/// a draft is never something to work from (flutter-app-design §5.5).
class DocumentListScreen extends ConsumerStatefulWidget {
  const DocumentListScreen({super.key});

  @override
  ConsumerState<DocumentListScreen> createState() => _DocumentListScreenState();
}

class _DocumentListScreenState extends ConsumerState<DocumentListScreen> {
  String _q = '';

  @override
  Widget build(BuildContext context) {
    final r = ref.watch(documentListProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Documents')),
      floatingActionButton: FloatingActionButton.extended(
        key: const Key('documents-new'),
        onPressed: () => context.push('/documents/new'),
        icon: const Icon(Icons.add),
        label: const Text('New document'),
      ),
      body: Column(children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
          child: TextField(
            key: const Key('documents-search'),
            decoration: const InputDecoration(prefixIcon: Icon(Icons.search), hintText: 'Search by title or code'),
            onChanged: (v) => setState(() => _q = v.trim().toLowerCase()),
          ),
        ),
        Expanded(
          child: r.when(
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (e, _) => ProblemView(e, onRetry: () => ref.invalidate(documentListProvider)),
            data: (all) {
              final shown = all
                  .where((d) => !d.retired)
                  .where((d) =>
                      _q.isEmpty || d.title.toLowerCase().contains(_q) || d.code.toLowerCase().contains(_q))
                  .toList();
              if (shown.isEmpty) return const Center(child: Text('No documents match.'));
              return RefreshIndicator(
                onRefresh: () async => ref.invalidate(documentListProvider),
                child: ListView.separated(
                  key: const Key('documents-list'),
                  padding: const EdgeInsets.only(bottom: 88),
                  itemCount: shown.length,
                  separatorBuilder: (_, _) => const Divider(height: 1),
                  itemBuilder: (context, i) => _DocumentTile(shown[i]),
                ),
              );
            },
          ),
        ),
      ]),
    );
  }
}

class _DocumentTile extends StatelessWidget {
  const _DocumentTile(this.d);

  final DocumentListItem d;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return ListTile(
      key: Key('document-${d.uid}'),
      leading: Icon(d.published ? Icons.description_outlined : Icons.edit_note,
          color: d.published ? theme.colorScheme.primary : theme.colorScheme.outline),
      title: Text(d.title, maxLines: 2, overflow: TextOverflow.ellipsis),
      subtitle: Text([d.code, d.published ? 'published' : 'not published yet'].join(' · ')),
      onTap: () => context.push('/document/${d.uid}'),
    );
  }
}
