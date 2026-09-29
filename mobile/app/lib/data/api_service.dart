import 'dart:convert';
import 'dart:io' show Platform;

import 'package:argus_api/api.dart' as api;
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:http/http.dart' as http;

import '../core/config.dart';
import '../core/problem.dart';
import '../core/session.dart';

/// The one door to the ARGUS API: the generated client, with the headers every request
/// carries (authentication, workspace, client version, device) and every failure turned into a
/// [Problem]. Nothing else in the app talks HTTP (flutter-app-design §2.2).
class ApiService {
  ApiService(this.config, this.sessionOf, {this.onProblem, this.ensureFresh, this.httpClient});

  final AppConfig config;
  final Session? Function() sessionOf;

  /// Told about every problem before it is thrown: revocation, a signed-out session and a client
  /// too old for the server are handled once, for the whole app, by whoever listens.
  final void Function(Problem problem)? onProblem;

  /// Called before each request, to refresh an access token that is about to expire.
  final Future<void> Function()? ensureFresh;

  /// The transport; replaced only in tests.
  final http.Client? httpClient;

  String get platform => kIsWeb ? 'web' : (Platform.isIOS ? 'ios' : Platform.isAndroid ? 'android' : 'other');

  String get base => config.apiBase.replaceAll(RegExp(r'/+$'), '');

  Map<String, String> headers({String? idempotencyKey, String? ifMatch}) {
    final s = sessionOf();
    return {
      'X-ARGUS-Client': 'flutter/${config.appVersion}/$platform',
      if (s != null) 'Authorization': 'Bearer ${s.accessToken}',
      if (s?.workspaceId != null) 'X-Workspace-Id': s!.workspaceId!,
      if (s?.deviceId != null) 'X-ARGUS-Device': s!.deviceId!,
      // A command keeps its key for every retry, so a lost answer never writes twice (§3.2).
      'Idempotency-Key': ?idempotencyKey,
      'If-Match': ?ifMatch,
    };
  }

  api.ApiClient _client({String? idempotencyKey, String? ifMatch}) {
    final c = api.ApiClient(basePath: base);
    if (httpClient != null) c.client = httpClient!;
    headers(idempotencyKey: idempotencyKey, ifMatch: ifMatch).forEach(c.addDefaultHeader);
    return c;
  }

  /// Run a call of the generated client, turning its failures into problems.
  Future<T> call<T>(Future<T?> Function(api.ApiClient c) body, {String? idempotencyKey, String? ifMatch}) async {
    if (ensureFresh != null) await ensureFresh!();
    Problem problem;
    try {
      final result = await body(_client(idempotencyKey: idempotencyKey, ifMatch: ifMatch));
      if (result != null) return result;
      problem = Problem(ProblemCode.notFound, 'Nothing was returned.');
    } on api.ApiException catch (e) {
      problem = _fromException(e);
    }
    onProblem?.call(problem);
    throw problem;
  }

  /// For operations whose response the contract leaves untyped: the generated client builds the
  /// request (path, parameters, headers) and the JSON body is decoded here, since the generated
  /// deserializer has no case for an untyped value.
  Future<Object?> json(Future<http.Response> Function(api.ApiClient c) body,
      {String? idempotencyKey, String? ifMatch}) async {
    final r = await raw((c) => body(c), idempotencyKey: idempotencyKey, ifMatch: ifMatch);
    return r.body;
  }

  /// Like [json], with the status and headers (`202` for a proposed transition, the `ETag`).
  Future<({int status, Object? body, Map<String, String> headers})> raw(
      Future<http.Response> Function(api.ApiClient c) body,
      {String? idempotencyKey, String? ifMatch}) async {
    if (ensureFresh != null) await ensureFresh!();
    Problem problem;
    try {
      final r = await body(_client(idempotencyKey: idempotencyKey, ifMatch: ifMatch));
      final text = utf8.decode(r.bodyBytes, allowMalformed: true);
      if (r.statusCode < 400) {
        return (status: r.statusCode, body: text.isEmpty ? null : jsonDecode(text), headers: r.headers);
      }
      problem = Problem.fromResponse(r.statusCode, text);
    } on api.ApiException catch (e) {
      problem = _fromException(e);
    } on FormatException {
      problem = Problem(ProblemCode.unknown, 'ARGUS sent a response this version cannot read.');
    }
    onProblem?.call(problem);
    throw problem;
  }

  /// One piece of a resumable upload, as raw bytes (the generated method cannot send them).
  Future<Object?> putBytes(String path, Map<String, String> query, List<int> bytes, {String? idempotencyKey}) async {
    if (ensureFresh != null) await ensureFresh!();
    final client = httpClient ?? http.Client();
    Problem problem;
    try {
      final r = await client.put(Uri.parse('$base$path').replace(queryParameters: query),
          headers: {...headers(idempotencyKey: idempotencyKey), 'Content-Type': 'application/octet-stream'},
          body: bytes);
      final text = utf8.decode(r.bodyBytes, allowMalformed: true);
      if (r.statusCode < 400) return text.isEmpty ? null : jsonDecode(text);
      problem = Problem.fromResponse(r.statusCode, text);
    } on http.ClientException {
      problem = Problem(ProblemCode.offline, 'ARGUS cannot be reached. Check the network and try again.');
    } finally {
      if (httpClient == null) client.close();
    }
    onProblem?.call(problem);
    throw problem;
  }

  Problem _fromException(api.ApiException e) => (e.code == 400 && e.innerException != null)
      ? Problem(ProblemCode.offline, 'ARGUS cannot be reached. Check the network and try again.')
      : Problem.fromResponse(e.code, e.message);

  api.WorkspacesApi workspaces(api.ApiClient c) => api.WorkspacesApi(c);
  api.FieldClientApi field(api.ApiClient c) => api.FieldClientApi(c);
  api.HubApi hub(api.ApiClient c) => api.HubApi(c);
  api.AssetsApi assets(api.ApiClient c) => api.AssetsApi(c);
  api.InstallationsApi installations(api.ApiClient c) => api.InstallationsApi(c);
  api.IssuesApi issues(api.ApiClient c) => api.IssuesApi(c);
  api.DocumentsApi documents(api.ApiClient c) => api.DocumentsApi(c);
  api.LookupApi lookup(api.ApiClient c) => api.LookupApi(c);
  api.MetaApi meta(api.ApiClient c) => api.MetaApi(c);
  api.IntakeApi intake(api.ApiClient c) => api.IntakeApi(c);
  api.UploadsApi uploads(api.ApiClient c) => api.UploadsApi(c);
  api.NotificationsApi notifications(api.ApiClient c) => api.NotificationsApi(c);
  api.SchemasApi schemas(api.ApiClient c) => api.SchemasApi(c);
}
