import 'dart:convert';

import 'package:http/http.dart' as http;

import '../core/config.dart';

/// A newer release of the app than this one, and where to download it.
class AvailableUpdate {
  const AvailableUpdate({required this.version, required this.url});

  final String version;
  final String url;
}

/// Whether [a] is a later version than [b] ("1.35.10" > "1.35.9"), compared part by part as numbers.
bool isNewerVersion(String a, String b) {
  List<int> parts(String v) => v.split(RegExp(r'[.+-]')).map((p) => int.tryParse(p) ?? 0).toList();
  final x = parts(a), y = parts(b);
  for (var i = 0; i < x.length || i < y.length; i++) {
    final p = i < x.length ? x[i] : 0, q = i < y.length ? y[i] : 0;
    if (p != q) return p > q;
  }
  return false;
}

/// The newest GitHub release, when it is newer than this build — only for a build published there
/// (`ARGUS_DISTRIBUTION=github`): the Play store updates its own, and a developer's build is not a release.
/// Any failure (offline, rate-limited) means "nothing to say", never an error shown to the person.
Future<AvailableUpdate?> checkForUpdate(AppConfig config, http.Client client) async {
  if (config.distribution != 'github') return null;
  try {
    final r = await client.get(Uri.parse('https://api.github.com/repos/${AppConfig.releasesRepo}/releases/latest'),
        headers: {'Accept': 'application/vnd.github+json'});
    if (r.statusCode != 200) return null;
    final release = jsonDecode(r.body) as Map<String, dynamic>;
    final version = (release['tag_name'] ?? '').toString().replaceFirst(RegExp('^v'), '');
    if (version.isEmpty || !isNewerVersion(version, config.appVersion)) return null;
    final apk = (release['assets'] as List? ?? const [])
        .whereType<Map>()
        .where((a) => (a['name'] ?? '').toString().endsWith('.apk'))
        .firstOrNull;
    final url = (apk?['browser_download_url'] ?? release['html_url'])?.toString();
    return url == null ? null : AvailableUpdate(version: version, url: url);
  } catch (_) {
    return null;
  }
}
