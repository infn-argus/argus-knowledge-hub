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

  api.ApiClient _client() {
    final c = api.ApiClient(basePath: config.apiBase.replaceAll(RegExp(r'/+$'), ''));
    if (httpClient != null) c.client = httpClient!;
    final s = sessionOf();
    c.addDefaultHeader('X-ARGUS-Client', 'flutter/${config.appVersion}/$platform');
    if (s != null) {
      c.addDefaultHeader('Authorization', 'Bearer ${s.accessToken}');
      if (s.workspaceId != null) c.addDefaultHeader('X-Workspace-Id', s.workspaceId!);
      if (s.deviceId != null) c.addDefaultHeader('X-ARGUS-Device', s.deviceId!);
    }
    return c;
  }

  /// Run a call of the generated client, turning its failures into problems.
  Future<T> call<T>(Future<T?> Function(api.ApiClient c) body) async {
    if (ensureFresh != null) await ensureFresh!();
    Problem problem;
    try {
      final result = await body(_client());
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
  Future<Object?> json(Future<http.Response> Function(api.ApiClient c) body) async {
    if (ensureFresh != null) await ensureFresh!();
    Problem problem;
    try {
      final r = await body(_client());
      final text = utf8.decode(r.bodyBytes, allowMalformed: true);
      if (r.statusCode < 400) return text.isEmpty ? null : jsonDecode(text);
      problem = Problem.fromResponse(r.statusCode, text);
    } on api.ApiException catch (e) {
      problem = _fromException(e);
    } on FormatException {
      problem = Problem(ProblemCode.unknown, 'ARGUS sent a response this version cannot read.');
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
}
