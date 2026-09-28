import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/providers.dart';
import '../../widgets/common.dart';

/// Where to work. Only workspaces the person can read are offered; the choice is sent with every
/// request and can be changed from the menu.
class WorkspaceScreen extends ConsumerWidget {
  const WorkspaceScreen({super.key, this.returnTo});

  final String? returnTo;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final rows = ref.watch(myWorkspacesProvider);
    final session = ref.watch(sessionProvider).value;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Choose a workspace'),
        actions: [
          TextButton(
            onPressed: () => ref.read(sessionProvider.notifier).signOut(),
            child: const Text('Sign out'),
          ),
        ],
      ),
      body: rows.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => ProblemView(e, onRetry: () => ref.invalidate(myWorkspacesProvider)),
        data: (list) => list.isEmpty
            ? const ProblemView('You cannot read any workspace. Ask an administrator for access.')
            : ListView(children: [
                if (session?.userLabel != null)
                  Padding(
                    padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
                    child: Text('Signed in as ${session!.userLabel}'),
                  ),
                for (final w in list)
                  ListTile(
                    key: Key('workspace-${w.id}'),
                    leading: const Icon(Icons.workspaces_outline),
                    title: Text(w.name),
                    subtitle: Text(w.canCreate ? 'Read and write' : 'Read only'),
                    selected: session?.workspaceId == w.id,
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () async {
                      await ref.read(sessionProvider.notifier).chooseWorkspace(w);
                      if (context.mounted) context.go(returnTo ?? '/');
                    },
                  ),
              ]),
      ),
    );
  }
}
