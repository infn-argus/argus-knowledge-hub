import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app/providers.dart';
import '../../data/caching_client.dart';
import '../../widgets/common.dart';

/// What the person can set about the app itself, as opposed to the records: how it looks, and what it
/// keeps on the device.
class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final mode = ref.watch(themeModeProvider);
    final config = ref.watch(configProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: ListView(children: [
        const SectionHeader('Appearance'),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          child: SegmentedButton<ThemeMode>(
            key: const Key('settings-theme'),
            segments: const [
              ButtonSegment(value: ThemeMode.system, icon: Icon(Icons.brightness_auto), label: Text('System')),
              ButtonSegment(value: ThemeMode.light, icon: Icon(Icons.light_mode), label: Text('Light')),
              ButtonSegment(value: ThemeMode.dark, icon: Icon(Icons.dark_mode), label: Text('Dark')),
            ],
            selected: {mode},
            onSelectionChanged: (s) => ref.read(themeModeProvider.notifier).set(s.first),
          ),
        ),
        const SectionHeader('On this device'),
        ListTile(
          leading: const Icon(Icons.offline_pin_outlined),
          title: const Text('Saved copies for offline use'),
          subtitle: Text('Records you open are kept, encrypted, for ${config.offlineRetentionDays} days, and shown '
              'when ARGUS cannot be reached. What you just saw is shown again for ${freshCopies.inSeconds} '
              'seconds without asking ARGUS; pull down on a list to refresh it.'),
          isThreeLine: true,
        ),
        ListTile(
          key: const Key('settings-clear-cache'),
          leading: const Icon(Icons.delete_sweep_outlined),
          title: const Text('Remove saved copies'),
          subtitle: const Text('Unsent changes are kept.'),
          onTap: () async {
            await ref.read(cacheStoreProvider).clear(CachingClient.prefix);
            if (context.mounted) {
              ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Saved copies removed.')));
            }
          },
        ),
      ]),
    );
  }
}
