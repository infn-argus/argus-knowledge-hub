import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'router.dart';

/// Field use: large targets, high contrast, a theme that follows the system (bright sun, dark
/// halls).
class ArgusFieldApp extends ConsumerWidget {
  const ArgusFieldApp({super.key});

  static ThemeData _theme(Brightness b) {
    final scheme = ColorScheme.fromSeed(seedColor: const Color(0xFF0B5CAD), brightness: b);
    return ThemeData(
      colorScheme: scheme,
      useMaterial3: true,
      visualDensity: VisualDensity.standard,
      materialTapTargetSize: MaterialTapTargetSize.padded,
      listTileTheme: const ListTileThemeData(minVerticalPadding: 10),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) => MaterialApp.router(
        title: 'ARGUS Field',
        debugShowCheckedModeBanner: false,
        theme: _theme(Brightness.light),
        darkTheme: _theme(Brightness.dark),
        routerConfig: ref.watch(routerProvider),
      );
}
