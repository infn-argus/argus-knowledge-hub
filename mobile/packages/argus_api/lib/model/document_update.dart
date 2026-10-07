//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of openapi.api;

class DocumentUpdate {
  /// Returns a new [DocumentUpdate] instance.
  DocumentUpdate({
    this.authorityLevel,
    this.confidentiality,
    this.documentTypeUid,
    this.isGlobal,
    this.ownerUserId,
    this.responsibleServiceAssetUid,
    this.title,
  });

  DocumentUpdateAuthorityLevelEnum? authorityLevel;

  DocumentUpdateConfidentialityEnum? confidentiality;

  String? documentTypeUid;

  bool? isGlobal;

  String? ownerUserId;

  String? responsibleServiceAssetUid;

  String? title;

  @override
  bool operator ==(Object other) => identical(this, other) || other is DocumentUpdate &&
    other.authorityLevel == authorityLevel &&
    other.confidentiality == confidentiality &&
    other.documentTypeUid == documentTypeUid &&
    other.isGlobal == isGlobal &&
    other.ownerUserId == ownerUserId &&
    other.responsibleServiceAssetUid == responsibleServiceAssetUid &&
    other.title == title;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (authorityLevel == null ? 0 : authorityLevel!.hashCode) +
    (confidentiality == null ? 0 : confidentiality!.hashCode) +
    (documentTypeUid == null ? 0 : documentTypeUid!.hashCode) +
    (isGlobal == null ? 0 : isGlobal!.hashCode) +
    (ownerUserId == null ? 0 : ownerUserId!.hashCode) +
    (responsibleServiceAssetUid == null ? 0 : responsibleServiceAssetUid!.hashCode) +
    (title == null ? 0 : title!.hashCode);

  @override
  String toString() => 'DocumentUpdate[authorityLevel=$authorityLevel, confidentiality=$confidentiality, documentTypeUid=$documentTypeUid, isGlobal=$isGlobal, ownerUserId=$ownerUserId, responsibleServiceAssetUid=$responsibleServiceAssetUid, title=$title]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
    if (this.authorityLevel != null) {
      json[r'authority_level'] = this.authorityLevel;
    } else {
      json[r'authority_level'] = null;
    }
    if (this.confidentiality != null) {
      json[r'confidentiality'] = this.confidentiality;
    } else {
      json[r'confidentiality'] = null;
    }
    if (this.documentTypeUid != null) {
      json[r'document_type_uid'] = this.documentTypeUid;
    } else {
      json[r'document_type_uid'] = null;
    }
    if (this.isGlobal != null) {
      json[r'is_global'] = this.isGlobal;
    } else {
      json[r'is_global'] = null;
    }
    if (this.ownerUserId != null) {
      json[r'owner_user_id'] = this.ownerUserId;
    } else {
      json[r'owner_user_id'] = null;
    }
    if (this.responsibleServiceAssetUid != null) {
      json[r'responsible_service_asset_uid'] = this.responsibleServiceAssetUid;
    } else {
      json[r'responsible_service_asset_uid'] = null;
    }
    if (this.title != null) {
      json[r'title'] = this.title;
    } else {
      json[r'title'] = null;
    }
    return json;
  }

  /// Returns a new [DocumentUpdate] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static DocumentUpdate? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        requiredKeys.forEach((key) {
          assert(json.containsKey(key), 'Required key "DocumentUpdate[$key]" is missing from JSON.');
          assert(json[key] != null, 'Required key "DocumentUpdate[$key]" has a null value in JSON.');
        });
        return true;
      }());

      return DocumentUpdate(
        authorityLevel: DocumentUpdateAuthorityLevelEnum.fromJson(json[r'authority_level']),
        confidentiality: DocumentUpdateConfidentialityEnum.fromJson(json[r'confidentiality']),
        documentTypeUid: mapValueOfType<String>(json, r'document_type_uid'),
        isGlobal: mapValueOfType<bool>(json, r'is_global'),
        ownerUserId: mapValueOfType<String>(json, r'owner_user_id'),
        responsibleServiceAssetUid: mapValueOfType<String>(json, r'responsible_service_asset_uid'),
        title: mapValueOfType<String>(json, r'title'),
      );
    }
    return null;
  }

  static List<DocumentUpdate> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <DocumentUpdate>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = DocumentUpdate.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, DocumentUpdate> mapFromJson(dynamic json) {
    final map = <String, DocumentUpdate>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = DocumentUpdate.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of DocumentUpdate-objects as value to a dart map
  static Map<String, List<DocumentUpdate>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<DocumentUpdate>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = DocumentUpdate.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
  };
}


class DocumentUpdateAuthorityLevelEnum {
  /// Instantiate a new enum with the provided [value].
  const DocumentUpdateAuthorityLevelEnum._(this.value);

  /// The underlying value of this enum member.
  final String value;

  @override
  String toString() => value;

  String toJson() => value;

  static const ufficiale = DocumentUpdateAuthorityLevelEnum._(r'ufficiale');
  static const informativo = DocumentUpdateAuthorityLevelEnum._(r'informativo');
  static const bozzaInterna = DocumentUpdateAuthorityLevelEnum._(r'bozza_interna');

  /// List of all possible values in this [enum][DocumentUpdateAuthorityLevelEnum].
  static const values = <DocumentUpdateAuthorityLevelEnum>[
    ufficiale,
    informativo,
    bozzaInterna,
  ];

  static DocumentUpdateAuthorityLevelEnum? fromJson(dynamic value) => DocumentUpdateAuthorityLevelEnumTypeTransformer().decode(value);

  static List<DocumentUpdateAuthorityLevelEnum> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <DocumentUpdateAuthorityLevelEnum>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = DocumentUpdateAuthorityLevelEnum.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }
}

/// Transformation class that can [encode] an instance of [DocumentUpdateAuthorityLevelEnum] to String,
/// and [decode] dynamic data back to [DocumentUpdateAuthorityLevelEnum].
class DocumentUpdateAuthorityLevelEnumTypeTransformer {
  factory DocumentUpdateAuthorityLevelEnumTypeTransformer() => _instance ??= const DocumentUpdateAuthorityLevelEnumTypeTransformer._();

  const DocumentUpdateAuthorityLevelEnumTypeTransformer._();

  String encode(DocumentUpdateAuthorityLevelEnum data) => data.value;

  /// Decodes a [dynamic value][data] to a DocumentUpdateAuthorityLevelEnum.
  ///
  /// If [allowNull] is true and the [dynamic value][data] cannot be decoded successfully,
  /// then null is returned. However, if [allowNull] is false and the [dynamic value][data]
  /// cannot be decoded successfully, then an [UnimplementedError] is thrown.
  ///
  /// The [allowNull] is very handy when an API changes and a new enum value is added or removed,
  /// and users are still using an old app with the old code.
  DocumentUpdateAuthorityLevelEnum? decode(dynamic data, {bool allowNull = true}) {
    if (data != null) {
      switch (data) {
        case r'ufficiale': return DocumentUpdateAuthorityLevelEnum.ufficiale;
        case r'informativo': return DocumentUpdateAuthorityLevelEnum.informativo;
        case r'bozza_interna': return DocumentUpdateAuthorityLevelEnum.bozzaInterna;
        default:
          if (!allowNull) {
            throw ArgumentError('Unknown enum value to decode: $data');
          }
      }
    }
    return null;
  }

  /// Singleton [DocumentUpdateAuthorityLevelEnumTypeTransformer] instance.
  static DocumentUpdateAuthorityLevelEnumTypeTransformer? _instance;
}



class DocumentUpdateConfidentialityEnum {
  /// Instantiate a new enum with the provided [value].
  const DocumentUpdateConfidentialityEnum._(this.value);

  /// The underlying value of this enum member.
  final String value;

  @override
  String toString() => value;

  String toJson() => value;

  static const pubblico = DocumentUpdateConfidentialityEnum._(r'pubblico');
  static const interno = DocumentUpdateConfidentialityEnum._(r'interno');
  static const riservato = DocumentUpdateConfidentialityEnum._(r'riservato');

  /// List of all possible values in this [enum][DocumentUpdateConfidentialityEnum].
  static const values = <DocumentUpdateConfidentialityEnum>[
    pubblico,
    interno,
    riservato,
  ];

  static DocumentUpdateConfidentialityEnum? fromJson(dynamic value) => DocumentUpdateConfidentialityEnumTypeTransformer().decode(value);

  static List<DocumentUpdateConfidentialityEnum> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <DocumentUpdateConfidentialityEnum>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = DocumentUpdateConfidentialityEnum.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }
}

/// Transformation class that can [encode] an instance of [DocumentUpdateConfidentialityEnum] to String,
/// and [decode] dynamic data back to [DocumentUpdateConfidentialityEnum].
class DocumentUpdateConfidentialityEnumTypeTransformer {
  factory DocumentUpdateConfidentialityEnumTypeTransformer() => _instance ??= const DocumentUpdateConfidentialityEnumTypeTransformer._();

  const DocumentUpdateConfidentialityEnumTypeTransformer._();

  String encode(DocumentUpdateConfidentialityEnum data) => data.value;

  /// Decodes a [dynamic value][data] to a DocumentUpdateConfidentialityEnum.
  ///
  /// If [allowNull] is true and the [dynamic value][data] cannot be decoded successfully,
  /// then null is returned. However, if [allowNull] is false and the [dynamic value][data]
  /// cannot be decoded successfully, then an [UnimplementedError] is thrown.
  ///
  /// The [allowNull] is very handy when an API changes and a new enum value is added or removed,
  /// and users are still using an old app with the old code.
  DocumentUpdateConfidentialityEnum? decode(dynamic data, {bool allowNull = true}) {
    if (data != null) {
      switch (data) {
        case r'pubblico': return DocumentUpdateConfidentialityEnum.pubblico;
        case r'interno': return DocumentUpdateConfidentialityEnum.interno;
        case r'riservato': return DocumentUpdateConfidentialityEnum.riservato;
        default:
          if (!allowNull) {
            throw ArgumentError('Unknown enum value to decode: $data');
          }
      }
    }
    return null;
  }

  /// Singleton [DocumentUpdateConfidentialityEnumTypeTransformer] instance.
  static DocumentUpdateConfidentialityEnumTypeTransformer? _instance;
}


