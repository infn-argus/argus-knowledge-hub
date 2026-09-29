//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of openapi.api;


class IntakeApi {
  IntakeApi([ApiClient? apiClient]) : apiClient = apiClient ?? defaultApiClient;

  final ApiClient apiClient;

  /// Assist From File
  ///
  /// Fill a draft from a file: a nameplate photo, a datasheet, a Word or Excel file, an email.
  ///
  /// Note: This method returns the HTTP [Response].
  ///
  /// Parameters:
  ///
  /// * [String] kind (required):
  ///
  /// * [MultipartFile] file (required):
  ///
  /// * [String] xWorkspaceId:
  ///
  /// * [String] authorization:
  ///
  /// * [String] draft:
  ///
  /// * [String] text:
  Future<Response> assistFromFileWithHttpInfo(String kind, MultipartFile file, { String? xWorkspaceId, String? authorization, String? draft, String? text, }) async {
    // ignore: prefer_const_declarations
    final path = r'/v1/intake/assist/{kind}/file'
      .replaceAll('{kind}', kind);

    // ignore: prefer_final_locals
    Object? postBody;

    final queryParams = <QueryParam>[];
    final headerParams = <String, String>{};
    final formParams = <String, String>{};

    if (xWorkspaceId != null) {
      headerParams[r'X-Workspace-Id'] = parameterToString(xWorkspaceId);
    }
    if (authorization != null) {
      headerParams[r'authorization'] = parameterToString(authorization);
    }

    const contentTypes = <String>['multipart/form-data'];

    bool hasFields = false;
    final mp = MultipartRequest('POST', Uri.parse(path));
    if (draft != null) {
      hasFields = true;
      mp.fields[r'draft'] = parameterToString(draft);
    }
    if (file != null) {
      hasFields = true;
      mp.fields[r'file'] = file.field;
      mp.files.add(file);
    }
    if (text != null) {
      hasFields = true;
      mp.fields[r'text'] = parameterToString(text);
    }
    if (hasFields) {
      postBody = mp;
    }

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

  /// Assist From File
  ///
  /// Fill a draft from a file: a nameplate photo, a datasheet, a Word or Excel file, an email.
  ///
  /// Parameters:
  ///
  /// * [String] kind (required):
  ///
  /// * [MultipartFile] file (required):
  ///
  /// * [String] xWorkspaceId:
  ///
  /// * [String] authorization:
  ///
  /// * [String] draft:
  ///
  /// * [String] text:
  Future<Object?> assistFromFile(String kind, MultipartFile file, { String? xWorkspaceId, String? authorization, String? draft, String? text, }) async {
    final response = await assistFromFileWithHttpInfo(kind, file,  xWorkspaceId: xWorkspaceId, authorization: authorization, draft: draft, text: text, );
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

  /// Assist Ticket
  ///
  /// Turn a report, in the person's own words, into a ticket draft.
  ///
  /// Note: This method returns the HTTP [Response].
  ///
  /// Parameters:
  ///
  /// * [AssistIn] assistIn (required):
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Response> assistTicketWithHttpInfo(AssistIn assistIn, { String? authorization, String? xWorkspaceId, }) async {
    // ignore: prefer_const_declarations
    final path = r'/v1/intake/assist/ticket';

    // ignore: prefer_final_locals
    Object? postBody = assistIn;

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

  /// Assist Ticket
  ///
  /// Turn a report, in the person's own words, into a ticket draft.
  ///
  /// Parameters:
  ///
  /// * [AssistIn] assistIn (required):
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Object?> assistTicket(AssistIn assistIn, { String? authorization, String? xWorkspaceId, }) async {
    final response = await assistTicketWithHttpInfo(assistIn,  authorization: authorization, xWorkspaceId: xWorkspaceId, );
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

  /// Decide Proposal
  ///
  /// Confirm, correct or reject an AI proposal. Confirming makes it the owner's own statement.
  ///
  /// Note: This method returns the HTTP [Response].
  ///
  /// Parameters:
  ///
  /// * [String] claimId (required):
  ///
  /// * [DecideIn] decideIn (required):
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Response> decideProposalWithHttpInfo(String claimId, DecideIn decideIn, { String? authorization, String? xWorkspaceId, }) async {
    // ignore: prefer_const_declarations
    final path = r'/v1/intake/proposals/{claim_id}'
      .replaceAll('{claim_id}', claimId);

    // ignore: prefer_final_locals
    Object? postBody = decideIn;

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

  /// Decide Proposal
  ///
  /// Confirm, correct or reject an AI proposal. Confirming makes it the owner's own statement.
  ///
  /// Parameters:
  ///
  /// * [String] claimId (required):
  ///
  /// * [DecideIn] decideIn (required):
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Object?> decideProposal(String claimId, DecideIn decideIn, { String? authorization, String? xWorkspaceId, }) async {
    final response = await decideProposalWithHttpInfo(claimId, decideIn,  authorization: authorization, xWorkspaceId: xWorkspaceId, );
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

  /// Guide Asset
  ///
  /// What is missing or wrong in this asset draft, and the next question.
  ///
  /// Note: This method returns the HTTP [Response].
  ///
  /// Parameters:
  ///
  /// * [GuideIn] guideIn (required):
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Response> guideAssetWithHttpInfo(GuideIn guideIn, { String? authorization, String? xWorkspaceId, }) async {
    // ignore: prefer_const_declarations
    final path = r'/v1/intake/guide/asset';

    // ignore: prefer_final_locals
    Object? postBody = guideIn;

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

  /// Guide Asset
  ///
  /// What is missing or wrong in this asset draft, and the next question.
  ///
  /// Parameters:
  ///
  /// * [GuideIn] guideIn (required):
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Object?> guideAsset(GuideIn guideIn, { String? authorization, String? xWorkspaceId, }) async {
    final response = await guideAssetWithHttpInfo(guideIn,  authorization: authorization, xWorkspaceId: xWorkspaceId, );
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

  /// Guide Ticket
  ///
  /// Note: This method returns the HTTP [Response].
  ///
  /// Parameters:
  ///
  /// * [GuideIn] guideIn (required):
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Response> guideTicketWithHttpInfo(GuideIn guideIn, { String? authorization, String? xWorkspaceId, }) async {
    // ignore: prefer_const_declarations
    final path = r'/v1/intake/guide/ticket';

    // ignore: prefer_final_locals
    Object? postBody = guideIn;

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

  /// Guide Ticket
  ///
  /// Parameters:
  ///
  /// * [GuideIn] guideIn (required):
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Object?> guideTicket(GuideIn guideIn, { String? authorization, String? xWorkspaceId, }) async {
    final response = await guideTicketWithHttpInfo(guideIn,  authorization: authorization, xWorkspaceId: xWorkspaceId, );
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

  /// Record Outcome
  ///
  /// After the save: which suggestions the person kept, corrected or left out.
  ///
  /// Note: This method returns the HTTP [Response].
  ///
  /// Parameters:
  ///
  /// * [String] runId (required):
  ///
  /// * [OutcomeIn] outcomeIn (required):
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Response> recordOutcomeWithHttpInfo(String runId, OutcomeIn outcomeIn, { String? authorization, String? xWorkspaceId, }) async {
    // ignore: prefer_const_declarations
    final path = r'/v1/intake/runs/{run_id}/outcome'
      .replaceAll('{run_id}', runId);

    // ignore: prefer_final_locals
    Object? postBody = outcomeIn;

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

  /// Record Outcome
  ///
  /// After the save: which suggestions the person kept, corrected or left out.
  ///
  /// Parameters:
  ///
  /// * [String] runId (required):
  ///
  /// * [OutcomeIn] outcomeIn (required):
  ///
  /// * [String] authorization:
  ///
  /// * [String] xWorkspaceId:
  Future<Object?> recordOutcome(String runId, OutcomeIn outcomeIn, { String? authorization, String? xWorkspaceId, }) async {
    final response = await recordOutcomeWithHttpInfo(runId, outcomeIn,  authorization: authorization, xWorkspaceId: xWorkspaceId, );
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
