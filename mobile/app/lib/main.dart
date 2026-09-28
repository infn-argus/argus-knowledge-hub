import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_web_plugins/url_strategy.dart';

import 'app/app.dart';
import 'app/providers.dart';

void main() {
  // On the web build, record links are plain paths (/asset/<uid>), the same as the web app's.
  usePathUrlStrategy();
  runApp(const ProviderScope(retry: retryPolicy, child: ArgusFieldApp()));
}
