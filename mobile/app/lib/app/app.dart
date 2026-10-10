import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../features/sync/sync_driver.dart';
import 'package:go_router/go_router.dart';

import '../features/notifications/phone_notifications.dart';
import 'providers.dart';
import 'router.dart';

/// Field use: large targets, high contrast, a theme that follows the system (bright sun, dark
/// halls).
class ArgusFieldApp extends ConsumerWidget {
  const ArgusFieldApp({super.key});

  static ThemeData _theme(Brightness b) {
    // The ARGUS icon's blue.
    final scheme = ColorScheme.fromSeed(seedColor: const Color(0xFF0B55B5), brightness: b);
    return ThemeData(
      colorScheme: scheme,
      useMaterial3: true,
      visualDensity: VisualDensity.standard,
      materialTapTargetSize: MaterialTapTargetSize.padded,
      listTileTheme: const ListTileThemeData(minVerticalPadding: 10),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(routerProvider);
    // A notification tapped opens what it is about: now, or once the app has started from it.
    onNotificationTapped = router.push;
    final launched = launchedFromNotification;
    if (launched != null) {
      launchedFromNotification = null;
      WidgetsBinding.instance.addPostFrameCallback((_) => router.push(launched));
    }
    return _app(ref, router);
  }

  Widget _app(WidgetRef ref, GoRouter router) => MaterialApp.router(
        title: 'ARGUS Field',
        debugShowCheckedModeBanner: false,
        theme: _theme(Brightness.light),
        darkTheme: _theme(Brightness.dark),
        themeMode: ref.watch(themeModeProvider),
        routerConfig: router,
        builder: (context, child) => SyncDriver(child: OfflineBanner(child: child ?? const SizedBox.shrink())),
      );
}
