//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of openapi.api;


class NotificationsApi {
  NotificationsApi([ApiClient? apiClient]) : apiClient = apiClient ?? defaultApiClient;

  final ApiClient apiClient;

  /// Follow Record
  ///
  /// Follow a piece of equipment or a document: each change to it becomes a notification, in whichever workspace it is.
  ///
  /// Note: This method returns the HTTP [Response].
  ///
  /// Parameters:
  ///
  /// * [String] subject (required):
  ///
  /// * [String] uid (required):
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Response> followRecordWithHttpInfo(String subject, String uid, { String? authorization, String? xWorkspaceId, }) async {
    // ignore: prefer_const_declarations
    final path = r'/v1/notifications/following/{subject}/{uid}'
      .replaceAll('{subject}', subject)
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
      'PUT',
      queryParams,
      postBody,
      headerParams,
      formParams,
      contentTypes.isEmpty ? null : contentTypes.first,
    );
  }

  /// Follow Record
  ///
  /// Follow a piece of equipment or a document: each change to it becomes a notification, in whichever workspace it is.
  ///
  /// Parameters:
  ///
  /// * [String] subject (required):
  ///
  /// * [String] uid (required):
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Object?> followRecord(String subject, String uid, { String? authorization, String? xWorkspaceId, }) async {
    final response = await followRecordWithHttpInfo(subject, uid,  authorization: authorization, xWorkspaceId: xWorkspaceId, );
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

  /// Following State
  ///
  /// Whether this person follows this piece of equipment or document, and how many do.
  ///
  /// Note: This method returns the HTTP [Response].
  ///
  /// Parameters:
  ///
  /// * [String] subject (required):
  ///
  /// * [String] uid (required):
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Response> followingStateWithHttpInfo(String subject, String uid, { String? authorization, String? xWorkspaceId, }) async {
    // ignore: prefer_const_declarations
    final path = r'/v1/notifications/following/{subject}/{uid}'
      .replaceAll('{subject}', subject)
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

  /// Following State
  ///
  /// Whether this person follows this piece of equipment or document, and how many do.
  ///
  /// Parameters:
  ///
  /// * [String] subject (required):
  ///
  /// * [String] uid (required):
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Object?> followingState(String subject, String uid, { String? authorization, String? xWorkspaceId, }) async {
    final response = await followingStateWithHttpInfo(subject, uid,  authorization: authorization, xWorkspaceId: xWorkspaceId, );
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

  /// Mark All Read Everywhere
  ///
  /// Every one of this person's notifications read, in every workspace.
  ///
  /// Note: This method returns the HTTP [Response].
  ///
  /// Parameters:
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Response> markAllReadEverywhereWithHttpInfo({ String? authorization, String? xWorkspaceId, }) async {
    // ignore: prefer_const_declarations
    final path = r'/v1/notifications/everywhere/read-all';

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
      'POST',
      queryParams,
      postBody,
      headerParams,
      formParams,
      contentTypes.isEmpty ? null : contentTypes.first,
    );
  }

  /// Mark All Read Everywhere
  ///
  /// Every one of this person's notifications read, in every workspace.
  ///
  /// Parameters:
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Object?> markAllReadEverywhere({ String? authorization, String? xWorkspaceId, }) async {
    final response = await markAllReadEverywhereWithHttpInfo( authorization: authorization, xWorkspaceId: xWorkspaceId, );
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

  /// Mark Read
  ///
  /// Note: This method returns the HTTP [Response].
  ///
  /// Parameters:
  ///
  /// * [int] nid (required):
  ///
  /// * [String] recipient:
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Response> markReadWithHttpInfo(int nid, { String? recipient, String? authorization, String? xWorkspaceId, }) async {
    // ignore: prefer_const_declarations
    final path = r'/v1/notifications/{nid}/read'
      .replaceAll('{nid}', nid.toString());

    // ignore: prefer_final_locals
    Object? postBody;

    final queryParams = <QueryParam>[];
    final headerParams = <String, String>{};
    final formParams = <String, String>{};

    if (recipient != null) {
      queryParams.addAll(_queryParams('', 'recipient', recipient));
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
      'POST',
      queryParams,
      postBody,
      headerParams,
      formParams,
      contentTypes.isEmpty ? null : contentTypes.first,
    );
  }

  /// Mark Read
  ///
  /// Parameters:
  ///
  /// * [int] nid (required):
  ///
  /// * [String] recipient:
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Object?> markRead(int nid, { String? recipient, String? authorization, String? xWorkspaceId, }) async {
    final response = await markReadWithHttpInfo(nid,  recipient: recipient, authorization: authorization, xWorkspaceId: xWorkspaceId, );
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

  /// Mark Read Everywhere
  ///
  /// One of this person's notifications read, whichever workspace it is from.
  ///
  /// Note: This method returns the HTTP [Response].
  ///
  /// Parameters:
  ///
  /// * [int] nid (required):
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Response> markReadEverywhereWithHttpInfo(int nid, { String? authorization, String? xWorkspaceId, }) async {
    // ignore: prefer_const_declarations
    final path = r'/v1/notifications/everywhere/{nid}/read'
      .replaceAll('{nid}', nid.toString());

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
      'POST',
      queryParams,
      postBody,
      headerParams,
      formParams,
      contentTypes.isEmpty ? null : contentTypes.first,
    );
  }

  /// Mark Read Everywhere
  ///
  /// One of this person's notifications read, whichever workspace it is from.
  ///
  /// Parameters:
  ///
  /// * [int] nid (required):
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Object?> markReadEverywhere(int nid, { String? authorization, String? xWorkspaceId, }) async {
    final response = await markReadEverywhereWithHttpInfo(nid,  authorization: authorization, xWorkspaceId: xWorkspaceId, );
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

  /// My Following
  ///
  /// What this person follows: equipment and documents, in every workspace.
  ///
  /// Note: This method returns the HTTP [Response].
  ///
  /// Parameters:
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Response> myFollowingWithHttpInfo({ String? authorization, String? xWorkspaceId, }) async {
    // ignore: prefer_const_declarations
    final path = r'/v1/notifications/following';

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

  /// My Following
  ///
  /// What this person follows: equipment and documents, in every workspace.
  ///
  /// Parameters:
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Object?> myFollowing({ String? authorization, String? xWorkspaceId, }) async {
    final response = await myFollowingWithHttpInfo( authorization: authorization, xWorkspaceId: xWorkspaceId, );
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

  /// My Notifications
  ///
  /// Note: This method returns the HTTP [Response].
  ///
  /// Parameters:
  ///
  /// * [bool] unread:
  ///
  /// * [String] recipient:
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Response> myNotificationsWithHttpInfo({ bool? unread, String? recipient, String? authorization, String? xWorkspaceId, }) async {
    // ignore: prefer_const_declarations
    final path = r'/v1/notifications';

    // ignore: prefer_final_locals
    Object? postBody;

    final queryParams = <QueryParam>[];
    final headerParams = <String, String>{};
    final formParams = <String, String>{};

    if (unread != null) {
      queryParams.addAll(_queryParams('', 'unread', unread));
    }
    if (recipient != null) {
      queryParams.addAll(_queryParams('', 'recipient', recipient));
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

  /// My Notifications
  ///
  /// Parameters:
  ///
  /// * [bool] unread:
  ///
  /// * [String] recipient:
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Object?> myNotifications({ bool? unread, String? recipient, String? authorization, String? xWorkspaceId, }) async {
    final response = await myNotificationsWithHttpInfo( unread: unread, recipient: recipient, authorization: authorization, xWorkspaceId: xWorkspaceId, );
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

  /// My Notifications Everywhere
  ///
  /// This person's notifications in every workspace they can still open. Unread and newer than `after` (the last id the phone has shown): what a background check turns into phone notifications. With `include_read`: the latest hundred, read or not, newest first — the inbox.
  ///
  /// Note: This method returns the HTTP [Response].
  ///
  /// Parameters:
  ///
  /// * [int] after:
  ///
  /// * [bool] includeRead:
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Response> myNotificationsEverywhereWithHttpInfo({ int? after, bool? includeRead, String? authorization, String? xWorkspaceId, }) async {
    // ignore: prefer_const_declarations
    final path = r'/v1/notifications/everywhere';

    // ignore: prefer_final_locals
    Object? postBody;

    final queryParams = <QueryParam>[];
    final headerParams = <String, String>{};
    final formParams = <String, String>{};

    if (after != null) {
      queryParams.addAll(_queryParams('', 'after', after));
    }
    if (includeRead != null) {
      queryParams.addAll(_queryParams('', 'include_read', includeRead));
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

  /// My Notifications Everywhere
  ///
  /// This person's notifications in every workspace they can still open. Unread and newer than `after` (the last id the phone has shown): what a background check turns into phone notifications. With `include_read`: the latest hundred, read or not, newest first — the inbox.
  ///
  /// Parameters:
  ///
  /// * [int] after:
  ///
  /// * [bool] includeRead:
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Object?> myNotificationsEverywhere({ int? after, bool? includeRead, String? authorization, String? xWorkspaceId, }) async {
    final response = await myNotificationsEverywhereWithHttpInfo( after: after, includeRead: includeRead, authorization: authorization, xWorkspaceId: xWorkspaceId, );
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

  /// My Subscriptions
  ///
  /// For each workspace this person can open, what they hear about there: every new ticket, every new or newly published document, every new piece of equipment. Off until chosen.
  ///
  /// Note: This method returns the HTTP [Response].
  ///
  /// Parameters:
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Response> mySubscriptionsWithHttpInfo({ String? authorization, String? xWorkspaceId, }) async {
    // ignore: prefer_const_declarations
    final path = r'/v1/notifications/subscriptions';

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

  /// My Subscriptions
  ///
  /// For each workspace this person can open, what they hear about there: every new ticket, every new or newly published document, every new piece of equipment. Off until chosen.
  ///
  /// Parameters:
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Object?> mySubscriptions({ String? authorization, String? xWorkspaceId, }) async {
    final response = await mySubscriptionsWithHttpInfo( authorization: authorization, xWorkspaceId: xWorkspaceId, );
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

  /// Set Subscription
  ///
  /// Note: This method returns the HTTP [Response].
  ///
  /// Parameters:
  ///
  /// * [String] workspaceId (required):
  ///
  /// * [SubscriptionIn] subscriptionIn (required):
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Response> setSubscriptionWithHttpInfo(String workspaceId, SubscriptionIn subscriptionIn, { String? authorization, String? xWorkspaceId, }) async {
    // ignore: prefer_const_declarations
    final path = r'/v1/notifications/subscriptions/{workspace_id}'
      .replaceAll('{workspace_id}', workspaceId);

    // ignore: prefer_final_locals
    Object? postBody = subscriptionIn;

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
      'PUT',
      queryParams,
      postBody,
      headerParams,
      formParams,
      contentTypes.isEmpty ? null : contentTypes.first,
    );
  }

  /// Set Subscription
  ///
  /// Parameters:
  ///
  /// * [String] workspaceId (required):
  ///
  /// * [SubscriptionIn] subscriptionIn (required):
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Object?> setSubscription(String workspaceId, SubscriptionIn subscriptionIn, { String? authorization, String? xWorkspaceId, }) async {
    final response = await setSubscriptionWithHttpInfo(workspaceId, subscriptionIn,  authorization: authorization, xWorkspaceId: xWorkspaceId, );
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

  /// Unfollow Record
  ///
  /// Note: This method returns the HTTP [Response].
  ///
  /// Parameters:
  ///
  /// * [String] subject (required):
  ///
  /// * [String] uid (required):
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Response> unfollowRecordWithHttpInfo(String subject, String uid, { String? authorization, String? xWorkspaceId, }) async {
    // ignore: prefer_const_declarations
    final path = r'/v1/notifications/following/{subject}/{uid}'
      .replaceAll('{subject}', subject)
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
      'DELETE',
      queryParams,
      postBody,
      headerParams,
      formParams,
      contentTypes.isEmpty ? null : contentTypes.first,
    );
  }

  /// Unfollow Record
  ///
  /// Parameters:
  ///
  /// * [String] subject (required):
  ///
  /// * [String] uid (required):
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Object?> unfollowRecord(String subject, String uid, { String? authorization, String? xWorkspaceId, }) async {
    final response = await unfollowRecordWithHttpInfo(subject, uid,  authorization: authorization, xWorkspaceId: xWorkspaceId, );
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
}
