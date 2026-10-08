import 'dart:async';
import 'dart:convert';

import 'package:crypto/crypto.dart' show sha256;
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart' show parseHttpDate;

import '../core/local_store.dart';

/// Keeps a copy of the records the person opened, and serves it when ARGUS cannot be reached
/// (flutter-app-design §5.1). It sits under the generated client, so every screen gets the same
/// behaviour without knowing about it.
///
/// - Only reads of records and of the person's own work are kept. Searches, lookups by label,
///   the assistant and uploads are never kept.
/// - A copy holds only what the server sent this person, so a restricted record they may not read
///   is never on the device (A72).
/// - A copy older than the offline retention (U22) is not served, and is removed.
/// - Every answer tells [onReachable] whether ARGUS answered, and [onServerTime] the server's clock,
///   so pending commands can be stamped in server time.
class CachingClient extends http.BaseClient {
  CachingClient(
    this._inner,
    this._store, {
    required this.retention,
    required this.scope,
    this.onReachable,
    this.onServerTime,
    this.maxEntries = 400,
    this.fresh = Duration.zero,
  });

  /// How long a copy is served instead of asking ARGUS again (U23): going back to a screen, or between
  /// tabs, need not cost a request. Any change sent from here (anything but a read) makes every copy taken
  /// before it stale, so what the person just did is never hidden by what they saw a moment earlier.
  final Duration fresh;
  DateTime _lastWrite = DateTime.fromMillisecondsSinceEpoch(0, isUtc: true);

  final http.Client _inner;
  final LocalStore _store;
  final Duration retention;

  /// Whose copies these are (workspace and person): another scope never sees them.
  final String Function() scope;
  final void Function(bool reachable)? onReachable;
  final void Function(DateTime serverNow)? onServerTime;
  final int maxEntries;

  static const prefix = 'argus.cache.';
  static const offlineHeader = 'x-argus-offline-copy';

  static final _kept = [
    RegExp(r'^/v1/me(/workspaces)?$'),
    RegExp(r'^/v1/assets/[^/]+$'),
    RegExp(r'^/v1/hub/(assets|tickets|documents)/[^/]+/context$'),
    RegExp(r'^/v1/installations$'),
    RegExp(r'^/v1/issues$'),
    RegExp(r'^/v1/issues/[^/]+(/(comments|attachments|transitions))?$'),
    RegExp(r'^/v1/documents/[^/]+(/current)?$'),
    RegExp(r'^/v1/schemas$'),
    RegExp(r'^/v1/ledger/review/mine$'),
    RegExp(r'^/v1/notifications$'),
    RegExp(r'^/v1/links/resolve$'),
  ];

  static bool keeps(Uri url) => _kept.any((r) => r.hasMatch(url.path));

  String _key(Uri url) => '$prefix${sha256.convert(utf8.encode('${scope()}|$url'))}';

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    final cacheable = request.method == 'GET' && keeps(request.url);
    if (request.method != 'GET' && request.method != 'HEAD') {
      _lastWrite = DateTime.now().toUtc();
    } else if (cacheable && fresh > Duration.zero) {
      final copy = await _copy(request.url, freshOnly: true);
      if (copy != null) return copy;
    }
    http.StreamedResponse response;
    try {
      response = await _inner.send(request);
    } catch (e) {
      if (e is! http.ClientException && e is! TimeoutException && !e.toString().contains('SocketException')) {
        rethrow;
      }
      onReachable?.call(false);
      if (cacheable) {
        final copy = await _copy(request.url);
        if (copy != null) return copy;
      }
      rethrow;
    }
    onReachable?.call(true);
    final date = response.headers['date'];
    if (date != null && onServerTime != null) {
      try {
        onServerTime!(parseHttpDate(date));
      } catch (_) {}
    }
    if (!cacheable || response.statusCode != 200) {
      // A record that is gone, or no longer visible, is gone from the device too.
      if (cacheable && (response.statusCode == 404 || response.statusCode == 403)) {
        await _store.delete(_key(request.url));
      }
      return response;
    }
    final bytes = await response.stream.toBytes();
    await _keep(request.url, response, bytes);
    return http.StreamedResponse(Stream.value(bytes), response.statusCode,
        headers: response.headers, request: response.request, reasonPhrase: response.reasonPhrase);
  }

  Future<void> _keep(Uri url, http.StreamedResponse r, List<int> bytes) async {
    await _store.write(
        _key(url),
        jsonEncode({
          'at': DateTime.now().toUtc().toIso8601String(),
          'type': r.headers['content-type'],
          'etag': r.headers['etag'],
          'body': base64Encode(bytes),
        }));
    await _evict();
  }

  Future<http.StreamedResponse?> _copy(Uri url, {bool freshOnly = false}) async {
    final raw = await _store.read(_key(url));
    if (raw == null) return null;
    final m = jsonDecode(raw) as Map<String, dynamic>;
    final at = DateTime.parse(m['at'] as String);
    if (freshOnly) {
      final now = DateTime.now().toUtc();
      if (now.difference(at) > fresh || !at.isAfter(_lastWrite)) return null;
      return http.StreamedResponse(Stream.value(base64Decode(m['body'] as String)), 200, headers: {
        'content-type': (m['type'] as String?) ?? 'application/json',
        if (m['etag'] != null) 'etag': m['etag'] as String,
      });
    }
    if (DateTime.now().toUtc().difference(at) > retention) {
      await _store.delete(_key(url)); // past the retention: hidden, then deleted (§5.6)
      return null;
    }
    final bytes = base64Decode(m['body'] as String);
    return http.StreamedResponse(Stream.value(bytes), 200, headers: {
      'content-type': (m['type'] as String?) ?? 'application/json',
      if (m['etag'] != null) 'etag': m['etag'] as String,
      offlineHeader: at.toIso8601String(),
    });
  }

  Future<void> _evict() async {
    final all = await _store.stamps(prefix);
    if (all.length <= maxEntries) return;
    final dated = all.entries.toList()..sort((a, b) => a.value.compareTo(b.value));
    for (final e in dated.take(all.length - maxEntries)) {
      await _store.forget(e.key);
    }
  }

  /// Remove copies past the retention (run at start and after a sync).
  Future<int> purge() async {
    var n = 0;
    for (final e in (await _store.stamps(prefix)).entries) {
      if (DateTime.now().toUtc().difference(e.value.toUtc()) > retention) {
        await _store.forget(e.key);
        n++;
      }
    }
    return n;
  }

  @override
  void close() => _inner.close();
}
