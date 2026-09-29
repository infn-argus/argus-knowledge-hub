//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of openapi.api;


class IssuesApi {
  IssuesApi([ApiClient? apiClient]) : apiClient = apiClient ?? defaultApiClient;

  final ApiClient apiClient;

  /// Create Issue
  ///
  /// Note: This method returns the HTTP [Response].
  ///
  /// Parameters:
  ///
  /// * [IssueCreate] issueCreate (required):
  ///
  /// * [String] xARGUSClient:
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Response> createIssueWithHttpInfo(IssueCreate issueCreate, { String? xARGUSClient, String? authorization, String? xWorkspaceId, }) async {
    // ignore: prefer_const_declarations
    final path = r'/v1/issues';

    // ignore: prefer_final_locals
    Object? postBody = issueCreate;

    final queryParams = <QueryParam>[];
    final headerParams = <String, String>{};
    final formParams = <String, String>{};

    if (xARGUSClient != null) {
      headerParams[r'X-ARGUS-Client'] = parameterToString(xARGUSClient);
    }
    if (authorization != null) {
      headerParams[r'authorization'] = parameterToString(authorization);
    }
    if (xWorkspaceId != null) {
      headerParams[r'X-Workspace-Id'] = parameterToString(xWorkspaceId);
    }

    const contentTypes = <String>['application/json'];


    return apiClient.invokeAPI(
      path,
      'POST',
      queryParams,
      postBody,
      headerParams,
      formParams,
      contentTypes.isEmpty ? null : contentTypes.first,
    );
  }

  /// Create Issue
  ///
  /// Parameters:
  ///
  /// * [IssueCreate] issueCreate (required):
  ///
  /// * [String] xARGUSClient:
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<IssueOut?> createIssue(IssueCreate issueCreate, { String? xARGUSClient, String? authorization, String? xWorkspaceId, }) async {
    final response = await createIssueWithHttpInfo(issueCreate,  xARGUSClient: xARGUSClient, authorization: authorization, xWorkspaceId: xWorkspaceId, );
    if (response.statusCode >= HttpStatus.badRequest) {
      throw ApiException(response.statusCode, await _decodeBodyBytes(response));
    }
    // When a remote server returns no body with a status of 204, we shall not decode it.
    // At the time of writing this, `dart:convert` will throw an "Unexpected end of input"
    // FormatException when trying to decode an empty string.
    if (response.body.isNotEmpty && response.statusCode != HttpStatus.noContent) {
      return await apiClient.deserializeAsync(await _decodeBodyBytes(response), 'IssueOut',) as IssueOut;
    
    }
    return null;
  }

  /// Create Issue Comment
  ///
  /// Note: This method returns the HTTP [Response].
  ///
  /// Parameters:
  ///
  /// * [String] uid (required):
  ///
  /// * [IssueCommentCreate] issueCommentCreate (required):
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Response> createIssueCommentWithHttpInfo(String uid, IssueCommentCreate issueCommentCreate, { String? authorization, String? xWorkspaceId, }) async {
    // ignore: prefer_const_declarations
    final path = r'/v1/issues/{uid}/comments'
      .replaceAll('{uid}', uid);

    // ignore: prefer_final_locals
    Object? postBody = issueCommentCreate;

    final queryParams = <QueryParam>[];
    final headerParams = <String, String>{};
    final formParams = <String, String>{};

    if (authorization != null) {
      headerParams[r'authorization'] = parameterToString(authorization);
    }
    if (xWorkspaceId != null) {
      headerParams[r'X-Workspace-Id'] = parameterToString(xWorkspaceId);
    }

    const contentTypes = <String>['application/json'];


    return apiClient.invokeAPI(
      path,
      'POST',
      queryParams,
      postBody,
      headerParams,
      formParams,
      contentTypes.isEmpty ? null : contentTypes.first,
    );
  }

  /// Create Issue Comment
  ///
  /// Parameters:
  ///
  /// * [String] uid (required):
  ///
  /// * [IssueCommentCreate] issueCommentCreate (required):
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<IssueCommentOut?> createIssueComment(String uid, IssueCommentCreate issueCommentCreate, { String? authorization, String? xWorkspaceId, }) async {
    final response = await createIssueCommentWithHttpInfo(uid, issueCommentCreate,  authorization: authorization, xWorkspaceId: xWorkspaceId, );
    if (response.statusCode >= HttpStatus.badRequest) {
      throw ApiException(response.statusCode, await _decodeBodyBytes(response));
    }
    // When a remote server returns no body with a status of 204, we shall not decode it.
    // At the time of writing this, `dart:convert` will throw an "Unexpected end of input"
    // FormatException when trying to decode an empty string.
    if (response.body.isNotEmpty && response.statusCode != HttpStatus.noContent) {
      return await apiClient.deserializeAsync(await _decodeBodyBytes(response), 'IssueCommentOut',) as IssueCommentOut;
    
    }
    return null;
  }

  /// Get Issue
  ///
  /// Note: This method returns the HTTP [Response].
  ///
  /// Parameters:
  ///
  /// * [String] uid (required):
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Response> getIssueWithHttpInfo(String uid, { String? authorization, String? xWorkspaceId, }) async {
    // ignore: prefer_const_declarations
    final path = r'/v1/issues/{uid}'
      .replaceAll('{uid}', uid);

    // ignore: prefer_final_locals
    Object? postBody;

    final queryParams = <QueryParam>[];
    final headerParams = <String, String>{};
    final formParams = <String, String>{};

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

  /// Get Issue
  ///
  /// Parameters:
  ///
  /// * [String] uid (required):
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<IssueOut?> getIssue(String uid, { String? authorization, String? xWorkspaceId, }) async {
    final response = await getIssueWithHttpInfo(uid,  authorization: authorization, xWorkspaceId: xWorkspaceId, );
    if (response.statusCode >= HttpStatus.badRequest) {
      throw ApiException(response.statusCode, await _decodeBodyBytes(response));
    }
    // When a remote server returns no body with a status of 204, we shall not decode it.
    // At the time of writing this, `dart:convert` will throw an "Unexpected end of input"
    // FormatException when trying to decode an empty string.
    if (response.body.isNotEmpty && response.statusCode != HttpStatus.noContent) {
      return await apiClient.deserializeAsync(await _decodeBodyBytes(response), 'IssueOut',) as IssueOut;
    
    }
    return null;
  }

  /// List Issue Attachments
  ///
  /// Note: This method returns the HTTP [Response].
  ///
  /// Parameters:
  ///
  /// * [String] uid (required):
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Response> listIssueAttachmentsWithHttpInfo(String uid, { String? authorization, String? xWorkspaceId, }) async {
    // ignore: prefer_const_declarations
    final path = r'/v1/issues/{uid}/attachments'
      .replaceAll('{uid}', uid);

    // ignore: prefer_final_locals
    Object? postBody;

    final queryParams = <QueryParam>[];
    final headerParams = <String, String>{};
    final formParams = <String, String>{};

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

  /// List Issue Attachments
  ///
  /// Parameters:
  ///
  /// * [String] uid (required):
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<List<AttachmentOut>?> listIssueAttachments(String uid, { String? authorization, String? xWorkspaceId, }) async {
    final response = await listIssueAttachmentsWithHttpInfo(uid,  authorization: authorization, xWorkspaceId: xWorkspaceId, );
    if (response.statusCode >= HttpStatus.badRequest) {
      throw ApiException(response.statusCode, await _decodeBodyBytes(response));
    }
    // When a remote server returns no body with a status of 204, we shall not decode it.
    // At the time of writing this, `dart:convert` will throw an "Unexpected end of input"
    // FormatException when trying to decode an empty string.
    if (response.body.isNotEmpty && response.statusCode != HttpStatus.noContent) {
      final responseBody = await _decodeBodyBytes(response);
      return (await apiClient.deserializeAsync(responseBody, 'List<AttachmentOut>') as List)
        .cast<AttachmentOut>()
        .toList(growable: false);

    }
    return null;
  }

  /// List Issue Comments
  ///
  /// Note: This method returns the HTTP [Response].
  ///
  /// Parameters:
  ///
  /// * [String] uid (required):
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Response> listIssueCommentsWithHttpInfo(String uid, { String? authorization, String? xWorkspaceId, }) async {
    // ignore: prefer_const_declarations
    final path = r'/v1/issues/{uid}/comments'
      .replaceAll('{uid}', uid);

    // ignore: prefer_final_locals
    Object? postBody;

    final queryParams = <QueryParam>[];
    final headerParams = <String, String>{};
    final formParams = <String, String>{};

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

  /// List Issue Comments
  ///
  /// Parameters:
  ///
  /// * [String] uid (required):
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<List<IssueCommentOut>?> listIssueComments(String uid, { String? authorization, String? xWorkspaceId, }) async {
    final response = await listIssueCommentsWithHttpInfo(uid,  authorization: authorization, xWorkspaceId: xWorkspaceId, );
    if (response.statusCode >= HttpStatus.badRequest) {
      throw ApiException(response.statusCode, await _decodeBodyBytes(response));
    }
    // When a remote server returns no body with a status of 204, we shall not decode it.
    // At the time of writing this, `dart:convert` will throw an "Unexpected end of input"
    // FormatException when trying to decode an empty string.
    if (response.body.isNotEmpty && response.statusCode != HttpStatus.noContent) {
      final responseBody = await _decodeBodyBytes(response);
      return (await apiClient.deserializeAsync(responseBody, 'List<IssueCommentOut>') as List)
        .cast<IssueCommentOut>()
        .toList(growable: false);

    }
    return null;
  }

  /// List Issues
  ///
  /// Note: This method returns the HTTP [Response].
  ///
  /// Parameters:
  ///
  /// * [String] schemaUid:
  ///
  /// * [bool] mine:
  ///   Only the open tickets assigned to the caller (the field client's prefetch)
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Response> listIssuesWithHttpInfo({ String? schemaUid, bool? mine, String? authorization, String? xWorkspaceId, }) async {
    // ignore: prefer_const_declarations
    final path = r'/v1/issues';

    // ignore: prefer_final_locals
    Object? postBody;

    final queryParams = <QueryParam>[];
    final headerParams = <String, String>{};
    final formParams = <String, String>{};

    if (schemaUid != null) {
      queryParams.addAll(_queryParams('', 'schema_uid', schemaUid));
    }
    if (mine != null) {
      queryParams.addAll(_queryParams('', 'mine', mine));
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

  /// List Issues
  ///
  /// Parameters:
  ///
  /// * [String] schemaUid:
  ///
  /// * [bool] mine:
  ///   Only the open tickets assigned to the caller (the field client's prefetch)
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<List<IssueOut>?> listIssues({ String? schemaUid, bool? mine, String? authorization, String? xWorkspaceId, }) async {
    final response = await listIssuesWithHttpInfo( schemaUid: schemaUid, mine: mine, authorization: authorization, xWorkspaceId: xWorkspaceId, );
    if (response.statusCode >= HttpStatus.badRequest) {
      throw ApiException(response.statusCode, await _decodeBodyBytes(response));
    }
    // When a remote server returns no body with a status of 204, we shall not decode it.
    // At the time of writing this, `dart:convert` will throw an "Unexpected end of input"
    // FormatException when trying to decode an empty string.
    if (response.body.isNotEmpty && response.statusCode != HttpStatus.noContent) {
      final responseBody = await _decodeBodyBytes(response);
      return (await apiClient.deserializeAsync(responseBody, 'List<IssueOut>') as List)
        .cast<IssueOut>()
        .toList(growable: false);

    }
    return null;
  }

  /// List Transitions
  ///
  /// Where this ticket can go next, and what each move needs.
  ///
  /// Note: This method returns the HTTP [Response].
  ///
  /// Parameters:
  ///
  /// * [String] uid (required):
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Response> listTransitionsWithHttpInfo(String uid, { String? authorization, String? xWorkspaceId, }) async {
    // ignore: prefer_const_declarations
    final path = r'/v1/issues/{uid}/transitions'
      .replaceAll('{uid}', uid);

    // ignore: prefer_final_locals
    Object? postBody;

    final queryParams = <QueryParam>[];
    final headerParams = <String, String>{};
    final formParams = <String, String>{};

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

  /// List Transitions
  ///
  /// Where this ticket can go next, and what each move needs.
  ///
  /// Parameters:
  ///
  /// * [String] uid (required):
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Object?> listTransitions(String uid, { String? authorization, String? xWorkspaceId, }) async {
    final response = await listTransitionsWithHttpInfo(uid,  authorization: authorization, xWorkspaceId: xWorkspaceId, );
    if (response.statusCode >= HttpStatus.badRequest) {
      throw ApiException(response.statusCode, await _decodeBodyBytes(response));
    }
    // When a remote server returns no body with a status of 204, we shall not decode it.
    // At the time of writing this, `dart:convert` will throw an "Unexpected end of input"
    // FormatException when trying to decode an empty string.
    if (response.body.isNotEmpty && response.statusCode != HttpStatus.noContent) {
      return await apiClient.deserializeAsync(await _decodeBodyBytes(response), 'Object',) as Object;
    
    }
    return null;
  }

  /// Transition Issue
  ///
  /// Note: This method returns the HTTP [Response].
  ///
  /// Parameters:
  ///
  /// * [String] uid (required):
  ///
  /// * [TransitionIn] transitionIn (required):
  ///
  /// * [String] ifMatch:
  ///   The ticket version read
  ///
  /// * [String] xARGUSClient:
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Response> transitionIssueWithHttpInfo(String uid, TransitionIn transitionIn, { String? ifMatch, String? xARGUSClient, String? authorization, String? xWorkspaceId, }) async {
    // ignore: prefer_const_declarations
    final path = r'/v1/issues/{uid}/transition'
      .replaceAll('{uid}', uid);

    // ignore: prefer_final_locals
    Object? postBody = transitionIn;

    final queryParams = <QueryParam>[];
    final headerParams = <String, String>{};
    final formParams = <String, String>{};

    if (ifMatch != null) {
      headerParams[r'If-Match'] = parameterToString(ifMatch);
    }
    if (xARGUSClient != null) {
      headerParams[r'X-ARGUS-Client'] = parameterToString(xARGUSClient);
    }
    if (authorization != null) {
      headerParams[r'authorization'] = parameterToString(authorization);
    }
    if (xWorkspaceId != null) {
      headerParams[r'X-Workspace-Id'] = parameterToString(xWorkspaceId);
    }

    const contentTypes = <String>['application/json'];


    return apiClient.invokeAPI(
      path,
      'POST',
      queryParams,
      postBody,
      headerParams,
      formParams,
      contentTypes.isEmpty ? null : contentTypes.first,
    );
  }

  /// Transition Issue
  ///
  /// Parameters:
  ///
  /// * [String] uid (required):
  ///
  /// * [TransitionIn] transitionIn (required):
  ///
  /// * [String] ifMatch:
  ///   The ticket version read
  ///
  /// * [String] xARGUSClient:
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<IssueOut?> transitionIssue(String uid, TransitionIn transitionIn, { String? ifMatch, String? xARGUSClient, String? authorization, String? xWorkspaceId, }) async {
    final response = await transitionIssueWithHttpInfo(uid, transitionIn,  ifMatch: ifMatch, xARGUSClient: xARGUSClient, authorization: authorization, xWorkspaceId: xWorkspaceId, );
    if (response.statusCode >= HttpStatus.badRequest) {
      throw ApiException(response.statusCode, await _decodeBodyBytes(response));
    }
    // When a remote server returns no body with a status of 204, we shall not decode it.
    // At the time of writing this, `dart:convert` will throw an "Unexpected end of input"
    // FormatException when trying to decode an empty string.
    if (response.body.isNotEmpty && response.statusCode != HttpStatus.noContent) {
      return await apiClient.deserializeAsync(await _decodeBodyBytes(response), 'IssueOut',) as IssueOut;
    
    }
    return null;
  }

  /// Update Issue
  ///
  /// Note: This method returns the HTTP [Response].
  ///
  /// Parameters:
  ///
  /// * [String] uid (required):
  ///
  /// * [IssueUpdate] issueUpdate (required):
  ///
  /// * [String] ifMatch:
  ///   The ticket version read (flutter-app-design §3.3)
  ///
  /// * [String] xARGUSClient:
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Response> updateIssueWithHttpInfo(String uid, IssueUpdate issueUpdate, { String? ifMatch, String? xARGUSClient, String? authorization, String? xWorkspaceId, }) async {
    // ignore: prefer_const_declarations
    final path = r'/v1/issues/{uid}'
      .replaceAll('{uid}', uid);

    // ignore: prefer_final_locals
    Object? postBody = issueUpdate;

    final queryParams = <QueryParam>[];
    final headerParams = <String, String>{};
    final formParams = <String, String>{};

    if (ifMatch != null) {
      headerParams[r'If-Match'] = parameterToString(ifMatch);
    }
    if (xARGUSClient != null) {
      headerParams[r'X-ARGUS-Client'] = parameterToString(xARGUSClient);
    }
    if (authorization != null) {
      headerParams[r'authorization'] = parameterToString(authorization);
    }
    if (xWorkspaceId != null) {
      headerParams[r'X-Workspace-Id'] = parameterToString(xWorkspaceId);
    }

    const contentTypes = <String>['application/json'];


    return apiClient.invokeAPI(
      path,
      'PUT',
      queryParams,
      postBody,
      headerParams,
      formParams,
      contentTypes.isEmpty ? null : contentTypes.first,
    );
  }

  /// Update Issue
  ///
  /// Parameters:
  ///
  /// * [String] uid (required):
  ///
  /// * [IssueUpdate] issueUpdate (required):
  ///
  /// * [String] ifMatch:
  ///   The ticket version read (flutter-app-design §3.3)
  ///
  /// * [String] xARGUSClient:
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<IssueOut?> updateIssue(String uid, IssueUpdate issueUpdate, { String? ifMatch, String? xARGUSClient, String? authorization, String? xWorkspaceId, }) async {
    final response = await updateIssueWithHttpInfo(uid, issueUpdate,  ifMatch: ifMatch, xARGUSClient: xARGUSClient, authorization: authorization, xWorkspaceId: xWorkspaceId, );
    if (response.statusCode >= HttpStatus.badRequest) {
      throw ApiException(response.statusCode, await _decodeBodyBytes(response));
    }
    // When a remote server returns no body with a status of 204, we shall not decode it.
    // At the time of writing this, `dart:convert` will throw an "Unexpected end of input"
    // FormatException when trying to decode an empty string.
    if (response.body.isNotEmpty && response.statusCode != HttpStatus.noContent) {
      return await apiClient.deserializeAsync(await _decodeBodyBytes(response), 'IssueOut',) as IssueOut;
    
    }
    return null;
  }
}
