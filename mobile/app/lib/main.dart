import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_web_plugins/url_strategy.dart';

import 'app/app.dart';
import 'app/providers.dart';
import 'features/notifications/phone_notifications.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // On the web build, record links are plain paths (/asset/<uid>), the same as the web app's.
  usePathUrlStrategy();
  // The app's own licence first on its licence page, before the packages it is built with.
  LicenseRegistry.addLicense(() async* {
    yield LicenseEntryWithLineBreaks(['ARGUS Field'], await rootBundle.loadString('LICENSE'));
  });
  // News shown on the phone while the app was closed: tapping one opens what it is about.
  await initPhoneNotifications();
  runApp(const ProviderScope(retry: retryPolicy, child: ArgusFieldApp()));
}
