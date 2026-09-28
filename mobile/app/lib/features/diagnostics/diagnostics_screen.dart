import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app/providers.dart';

/// What support asks for (flutter-app-design §9): versions, environment, device registration and
/// whether the server answers. No token, no personal data beyond the signed-in label.
class DiagnosticsScreen extends ConsumerWidget {
  const DiagnosticsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final config = ref.watch(configProvider);
    final session = ref.watch(sessionProvider).value;
    final api = ref.watch(apiServiceProvider);
    final meta = ref.watch(serverMetaProvider);
    Widget row(String k, String? v) => ListTile(dense: true, title: Text(k), subtitle: SelectableText(v ?? '—'));
    return Scaffold(
      appBar: AppBar(title: const Text('About and diagnostics')),
      body: ListView(children: [
        row('App version', config.appVersion),
        row('Client header', 'flutter/${config.appVersion}/${api.platform}'),
        row('Environment', config.environment),
        row('Server', config.apiBase),
        row('Signed in as', session?.userLabel),
        row('Sign-in method', session?.authType),
        row('Workspace', session?.workspaceName),
        row('Device registration', session?.deviceId),
        meta.when(
          loading: () => const ListTile(dense: true, title: Text('Server API'), subtitle: Text('checking…')),
          error: (e, _) => ListTile(dense: true, title: const Text('Server API'), subtitle: Text('unreachable: $e')),
          data: (m) => row('Server API', [m['current'] ?? m['version'], if (m['supported'] != null) 'supported ${m['supported']}']
              .whereType<Object>()
              .join(' · ')),
        ),
      ]),
    );
  }
}
