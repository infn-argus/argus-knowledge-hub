//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of openapi.api;


class GlobalValuesApi {
  GlobalValuesApi([ApiClient? apiClient]) : apiClient = apiClient ?? defaultApiClient;

  final ApiClient apiClient;

  /// List Global Values
  ///
  /// Note: This method returns the HTTP [Response].
  ///
  /// Parameters:
  ///
  /// * [String] appliesTo:
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Response> listGlobalValuesWithHttpInfo({ String? appliesTo, String? authorization, String? xWorkspaceId, }) async {
    // ignore: prefer_const_declarations
    final path = r'/v1/global-values';

    // ignore: prefer_final_locals
    Object? postBody;

    final queryParams = <QueryParam>[];
    final headerParams = <String, String>{};
    final formParams = <String, String>{};

    if (appliesTo != null) {
      queryParams.addAll(_queryParams('', 'applies_to', appliesTo));
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

  /// List Global Values
  ///
  /// Parameters:
  ///
  /// * [String] appliesTo:
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<List<GlobalValueOut>?> listGlobalValues({ String? appliesTo, String? authorization, String? xWorkspaceId, }) async {
    final response = await listGlobalValuesWithHttpInfo( appliesTo: appliesTo, authorization: authorization, xWorkspaceId: xWorkspaceId, );
    if (response.statusCode >= HttpStatus.badRequest) {
      throw ApiException(response.statusCode, await _decodeBodyBytes(response));
    }
    // When a remote server returns no body with a status of 204, we shall not decode it.
    // At the time of writing this, `dart:convert` will throw an "Unexpected end of input"
    // FormatException when trying to decode an empty string.
    if (response.body.isNotEmpty && response.statusCode != HttpStatus.noContent) {
      final responseBody = await _decodeBodyBytes(response);
      return (await apiClient.deserializeAsync(responseBody, 'List<GlobalValueOut>') as List)
        .cast<GlobalValueOut>()
        .toList(growable: false);

    }
    return null;
  }
}
