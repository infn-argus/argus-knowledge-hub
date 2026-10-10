//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of openapi.api;


class GraphApi {
  GraphApi([ApiClient? apiClient]) : apiClient = apiClient ?? defaultApiClient;

  final ApiClient apiClient;

  /// Get Graph
  ///
  /// Everything within `depth` hops of one node, across objects, tickets, documents and people.  Depth is capped at 4 deliberately: in a real inventory a hub object reaches most of the graph by the third hop, and an answer that large helps nobody.
  ///
  /// Note: This method returns the HTTP [Response].
  ///
  /// Parameters:
  ///
  /// * [String] kind (required):
  ///   asset | ticket | document | group | person
  ///
  /// * [String] uid (required):
  ///   The node to start from
  ///
  /// * [int] depth:
  ///
  /// * [String] kinds:
  ///   Comma-separated node kinds to keep, e.g. 'asset,document'
  ///
  /// * [int] maxNodes:
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Response> getGraphWithHttpInfo(String kind, String uid, { int? depth, String? kinds, int? maxNodes, String? authorization, String? xWorkspaceId, }) async {
    // ignore: prefer_const_declarations
    final path = r'/v1/graph';

    // ignore: prefer_final_locals
    Object? postBody;

    final queryParams = <QueryParam>[];
    final headerParams = <String, String>{};
    final formParams = <String, String>{};

      queryParams.addAll(_queryParams('', 'kind', kind));
      queryParams.addAll(_queryParams('', 'uid', uid));
    if (depth != null) {
      queryParams.addAll(_queryParams('', 'depth', depth));
    }
    if (kinds != null) {
      queryParams.addAll(_queryParams('', 'kinds', kinds));
    }
    if (maxNodes != null) {
      queryParams.addAll(_queryParams('', 'max_nodes', maxNodes));
    }

    if (authorization != null) {
      headerParams[r'authorization'] = parameterToString(authorization);
    }
    if (xWorkspaceId != null) {
      headerParams[r'X-Workspace-Id'] = parameterToString(xWorkspaceId);
    }

    const contentTypes = <String>[];


    return apiClient.invokeAPI(
      path,
      'GET',
      queryParams,
      postBody,
      headerParams,
      formParams,
      contentTypes.isEmpty ? null : contentTypes.first,
    );
  }

  /// Get Graph
  ///
  /// Everything within `depth` hops of one node, across objects, tickets, documents and people.  Depth is capped at 4 deliberately: in a real inventory a hub object reaches most of the graph by the third hop, and an answer that large helps nobody.
  ///
  /// Parameters:
  ///
  /// * [String] kind (required):
  ///   asset | ticket | document | group | person
  ///
  /// * [String] uid (required):
  ///   The node to start from
  ///
  /// * [int] depth:
  ///
  /// * [String] kinds:
  ///   Comma-separated node kinds to keep, e.g. 'asset,document'
  ///
  /// * [int] maxNodes:
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<GraphOut?> getGraph(String kind, String uid, { int? depth, String? kinds, int? maxNodes, String? authorization, String? xWorkspaceId, }) async {
    final response = await getGraphWithHttpInfo(kind, uid,  depth: depth, kinds: kinds, maxNodes: maxNodes, authorization: authorization, xWorkspaceId: xWorkspaceId, );
    if (response.statusCode >= HttpStatus.badRequest) {
      throw ApiException(response.statusCode, await _decodeBodyBytes(response));
    }
    // When a remote server returns no body with a status of 204, we shall not decode it.
    // At the time of writing this, `dart:convert` will throw an "Unexpected end of input"
    // FormatException when trying to decode an empty string.
    if (response.body.isNotEmpty && response.statusCode != HttpStatus.noContent) {
      return await apiClient.deserializeAsync(await _decodeBodyBytes(response), 'GraphOut',) as GraphOut;
    
    }
    return null;
  }

  /// Get Semantic Graph
  ///
  /// The semantic graph around one record: the records whose indexed text (procedures, tickets and their comments, comments on equipment, attached files) is closest in meaning to its own, from the knowledge index Ask ARGUS searches — what the relation graph cannot show, because nobody linked them.
  ///
  /// Note: This method returns the HTTP [Response].
  ///
  /// Parameters:
  ///
  /// * [String] kind (required):
  ///
  /// * [String] uid (required):
  ///   The record to start from
  ///
  /// * [int] limit:
  ///
  /// * [num] minScore:
  ///   How close, 0 to 1, a record must be to be shown
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Response> getSemanticGraphWithHttpInfo(String kind, String uid, { int? limit, num? minScore, String? authorization, String? xWorkspaceId, }) async {
    // ignore: prefer_const_declarations
    final path = r'/v1/graph/semantic';

    // ignore: prefer_final_locals
    Object? postBody;

    final queryParams = <QueryParam>[];
    final headerParams = <String, String>{};
    final formParams = <String, String>{};

      queryParams.addAll(_queryParams('', 'kind', kind));
      queryParams.addAll(_queryParams('', 'uid', uid));
    if (limit != null) {
      queryParams.addAll(_queryParams('', 'limit', limit));
    }
    if (minScore != null) {
      queryParams.addAll(_queryParams('', 'min_score', minScore));
    }

    if (authorization != null) {
      headerParams[r'authorization'] = parameterToString(authorization);
    }
    if (xWorkspaceId != null) {
      headerParams[r'X-Workspace-Id'] = parameterToString(xWorkspaceId);
    }

    const contentTypes = <String>[];


    return apiClient.invokeAPI(
      path,
      'GET',
      queryParams,
      postBody,
      headerParams,
      formParams,
      contentTypes.isEmpty ? null : contentTypes.first,
    );
  }

  /// Get Semantic Graph
  ///
  /// The semantic graph around one record: the records whose indexed text (procedures, tickets and their comments, comments on equipment, attached files) is closest in meaning to its own, from the knowledge index Ask ARGUS searches — what the relation graph cannot show, because nobody linked them.
  ///
  /// Parameters:
  ///
  /// * [String] kind (required):
  ///
  /// * [String] uid (required):
  ///   The record to start from
  ///
  /// * [int] limit:
  ///
  /// * [num] minScore:
  ///   How close, 0 to 1, a record must be to be shown
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<SemanticGraphOut?> getSemanticGraph(String kind, String uid, { int? limit, num? minScore, String? authorization, String? xWorkspaceId, }) async {
    final response = await getSemanticGraphWithHttpInfo(kind, uid,  limit: limit, minScore: minScore, authorization: authorization, xWorkspaceId: xWorkspaceId, );
    if (response.statusCode >= HttpStatus.badRequest) {
      throw ApiException(response.statusCode, await _decodeBodyBytes(response));
    }
    // When a remote server returns no body with a status of 204, we shall not decode it.
    // At the time of writing this, `dart:convert` will throw an "Unexpected end of input"
    // FormatException when trying to decode an empty string.
    if (response.body.isNotEmpty && response.statusCode != HttpStatus.noContent) {
      return await apiClient.deserializeAsync(await _decodeBodyBytes(response), 'SemanticGraphOut',) as SemanticGraphOut;
    
    }
    return null;
  }
}
