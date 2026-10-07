//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of openapi.api;

class DocumentCreate {
  /// Returns a new [DocumentCreate] instance.
  DocumentCreate({
    this.attributes,
    this.authorityLevel,
    this.bodyMarkdown,
    this.code,
    this.confidentiality,
    this.documentTypeUid,
    this.nextReviewDue,
    this.ownerUserId,
    this.responsibleServiceAssetUid,
    this.retentionClass = '5y',
    this.source_ = 'manual',
    this.steps,
    required this.title,
    required this.uid,
    this.validFrom,
    this.validUntil,
  });

  ///
  /// Please note: This property should have been non-nullable! Since the specification file
  /// does not include a default value (using the "default:" property), however, the generated
  /// source code must fall back to having a nullable type.
  /// Consider adding a "default:" property in the specification file to hide this note.
  ///
  Object? attributes;

  DocumentCreateAuthorityLevelEnum? authorityLevel;

  String? bodyMarkdown;

  String? code;

  DocumentCreateConfidentialityEnum? confidentiality;

  String? documentTypeUid;

  DateTime? nextReviewDue;

  String? ownerUserId;

  String? responsibleServiceAssetUid;

  String retentionClass;

  String source_;

  Object? steps;

  String title;

  String uid;

  DateTime? validFrom;

  DateTime? validUntil;

  @override
  bool operator ==(Object other) => identical(this, other) || other is DocumentCreate &&
    other.attributes == attributes &&
    other.authorityLevel == authorityLevel &&
    other.bodyMarkdown == bodyMarkdown &&
    other.code == code &&
    other.confidentiality == confidentiality &&
    other.documentTypeUid == documentTypeUid &&
    other.nextReviewDue == nextReviewDue &&
    other.ownerUserId == ownerUserId &&
    other.responsibleServiceAssetUid == responsibleServiceAssetUid &&
    other.retentionClass == retentionClass &&
    other.source_ == source_ &&
    other.steps == steps &&
    other.title == title &&
    other.uid == uid &&
    other.validFrom == validFrom &&
    other.validUntil == validUntil;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (attributes == null ? 0 : attributes!.hashCode) +
    (authorityLevel == null ? 0 : authorityLevel!.hashCode) +
    (bodyMarkdown == null ? 0 : bodyMarkdown!.hashCode) +
    (code == null ? 0 : code!.hashCode) +
    (confidentiality == null ? 0 : confidentiality!.hashCode) +
    (documentTypeUid == null ? 0 : documentTypeUid!.hashCode) +
    (nextReviewDue == null ? 0 : nextReviewDue!.hashCode) +
    (ownerUserId == null ? 0 : ownerUserId!.hashCode) +
    (responsibleServiceAssetUid == null ? 0 : responsibleServiceAssetUid!.hashCode) +
    (retentionClass.hashCode) +
    (source_.hashCode) +
    (steps == null ? 0 : steps!.hashCode) +
    (title.hashCode) +
    (uid.hashCode) +
    (validFrom == null ? 0 : validFrom!.hashCode) +
    (validUntil == null ? 0 : validUntil!.hashCode);

  @override
  String toString() => 'DocumentCreate[attributes=$attributes, authorityLevel=$authorityLevel, bodyMarkdown=$bodyMarkdown, code=$code, confidentiality=$confidentiality, documentTypeUid=$documentTypeUid, nextReviewDue=$nextReviewDue, ownerUserId=$ownerUserId, responsibleServiceAssetUid=$responsibleServiceAssetUid, retentionClass=$retentionClass, source_=$source_, steps=$steps, title=$title, uid=$uid, validFrom=$validFrom, validUntil=$validUntil]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
    if (this.attributes != null) {
      json[r'attributes'] = this.attributes;
    } else {
      json[r'attributes'] = null;
    }
    if (this.authorityLevel != null) {
      json[r'authority_level'] = this.authorityLevel;
    } else {
      json[r'authority_level'] = null;
    }
    if (this.bodyMarkdown != null) {
      json[r'body_markdown'] = this.bodyMarkdown;
    } else {
      json[r'body_markdown'] = null;
    }
    if (this.code != null) {
      json[r'code'] = this.code;
    } else {
      json[r'code'] = null;
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
    if (this.nextReviewDue != null) {
      json[r'next_review_due'] = _dateFormatter.format(this.nextReviewDue!.toUtc());
    } else {
      json[r'next_review_due'] = null;
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
      json[r'retention_class'] = this.retentionClass;
      json[r'source'] = this.source_;
    if (this.steps != null) {
      json[r'steps'] = this.steps;
    } else {
      json[r'steps'] = null;
    }
      json[r'title'] = this.title;
      json[r'uid'] = this.uid;
    if (this.validFrom != null) {
      json[r'valid_from'] = _dateFormatter.format(this.validFrom!.toUtc());
    } else {
      json[r'valid_from'] = null;
    }
    if (this.validUntil != null) {
      json[r'valid_until'] = _dateFormatter.format(this.validUntil!.toUtc());
    } else {
      json[r'valid_until'] = null;
    }
    return json;
  }

  /// Returns a new [DocumentCreate] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static DocumentCreate? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        requiredKeys.forEach((key) {
          assert(json.containsKey(key), 'Required key "DocumentCreate[$key]" is missing from JSON.');
          assert(json[key] != null, 'Required key "DocumentCreate[$key]" has a null value in JSON.');
        });
        return true;
      }());

      return DocumentCreate(
        attributes: mapValueOfType<Object>(json, r'attributes'),
        authorityLevel: DocumentCreateAuthorityLevelEnum.fromJson(json[r'authority_level']),
        bodyMarkdown: mapValueOfType<String>(json, r'body_markdown'),
        code: mapValueOfType<String>(json, r'code'),
        confidentiality: DocumentCreateConfidentialityEnum.fromJson(json[r'confidentiality']),
        documentTypeUid: mapValueOfType<String>(json, r'document_type_uid'),
        nextReviewDue: mapDateTime(json, r'next_review_due', r''),
        ownerUserId: mapValueOfType<String>(json, r'owner_user_id'),
        responsibleServiceAssetUid: mapValueOfType<String>(json, r'responsible_service_asset_uid'),
        retentionClass: mapValueOfType<String>(json, r'retention_class') ?? '5y',
        source_: mapValueOfType<String>(json, r'source') ?? 'manual',
        steps: mapValueOfType<Object>(json, r'steps'),
        title: mapValueOfType<String>(json, r'title')!,
        uid: mapValueOfType<String>(json, r'uid')!,
        validFrom: mapDateTime(json, r'valid_from', r''),
        validUntil: mapDateTime(json, r'valid_until', r''),
      );
    }
    return null;
  }

  static List<DocumentCreate> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <DocumentCreate>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = DocumentCreate.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, DocumentCreate> mapFromJson(dynamic json) {
    final map = <String, DocumentCreate>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = DocumentCreate.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of DocumentCreate-objects as value to a dart map
  static Map<String, List<DocumentCreate>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<DocumentCreate>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = DocumentCreate.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'title',
    'uid',
  };
}


class DocumentCreateAuthorityLevelEnum {
  /// Instantiate a new enum with the provided [value].
  const DocumentCreateAuthorityLevelEnum._(this.value);

  /// The underlying value of this enum member.
  final String value;

  @override
  String toString() => value;

  String toJson() => value;

  static const ufficiale = DocumentCreateAuthorityLevelEnum._(r'ufficiale');
  static const informativo = DocumentCreateAuthorityLevelEnum._(r'informativo');
  static const bozzaInterna = DocumentCreateAuthorityLevelEnum._(r'bozza_interna');

  /// List of all possible values in this [enum][DocumentCreateAuthorityLevelEnum].
  static const values = <DocumentCreateAuthorityLevelEnum>[
    ufficiale,
    informativo,
    bozzaInterna,
  ];

  static DocumentCreateAuthorityLevelEnum? fromJson(dynamic value) => DocumentCreateAuthorityLevelEnumTypeTransformer().decode(value);

  static List<DocumentCreateAuthorityLevelEnum> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <DocumentCreateAuthorityLevelEnum>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = DocumentCreateAuthorityLevelEnum.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }
}

/// Transformation class that can [encode] an instance of [DocumentCreateAuthorityLevelEnum] to String,
/// and [decode] dynamic data back to [DocumentCreateAuthorityLevelEnum].
class DocumentCreateAuthorityLevelEnumTypeTransformer {
  factory DocumentCreateAuthorityLevelEnumTypeTransformer() => _instance ??= const DocumentCreateAuthorityLevelEnumTypeTransformer._();

  const DocumentCreateAuthorityLevelEnumTypeTransformer._();

  String encode(DocumentCreateAuthorityLevelEnum data) => data.value;

  /// Decodes a [dynamic value][data] to a DocumentCreateAuthorityLevelEnum.
  ///
  /// If [allowNull] is true and the [dynamic value][data] cannot be decoded successfully,
  /// then null is returned. However, if [allowNull] is false and the [dynamic value][data]
  /// cannot be decoded successfully, then an [UnimplementedError] is thrown.
  ///
  /// The [allowNull] is very handy when an API changes and a new enum value is added or removed,
  /// and users are still using an old app with the old code.
  DocumentCreateAuthorityLevelEnum? decode(dynamic data, {bool allowNull = true}) {
    if (data != null) {
      switch (data) {
        case r'ufficiale': return DocumentCreateAuthorityLevelEnum.ufficiale;
        case r'informativo': return DocumentCreateAuthorityLevelEnum.informativo;
        case r'bozza_interna': return DocumentCreateAuthorityLevelEnum.bozzaInterna;
        default:
          if (!allowNull) {
            throw ArgumentError('Unknown enum value to decode: $data');
          }
      }
    }
    return null;
  }

  /// Singleton [DocumentCreateAuthorityLevelEnumTypeTransformer] instance.
  static DocumentCreateAuthorityLevelEnumTypeTransformer? _instance;
}



class DocumentCreateConfidentialityEnum {
  /// Instantiate a new enum with the provided [value].
  const DocumentCreateConfidentialityEnum._(this.value);

  /// The underlying value of this enum member.
  final String value;

  @override
  String toString() => value;

  String toJson() => value;

  static const pubblico = DocumentCreateConfidentialityEnum._(r'pubblico');
  static const interno = DocumentCreateConfidentialityEnum._(r'interno');
  static const riservato = DocumentCreateConfidentialityEnum._(r'riservato');

  /// List of all possible values in this [enum][DocumentCreateConfidentialityEnum].
  static const values = <DocumentCreateConfidentialityEnum>[
    pubblico,
    interno,
    riservato,
  ];

  static DocumentCreateConfidentialityEnum? fromJson(dynamic value) => DocumentCreateConfidentialityEnumTypeTransformer().decode(value);

  static List<DocumentCreateConfidentialityEnum> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <DocumentCreateConfidentialityEnum>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = DocumentCreateConfidentialityEnum.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }
}

/// Transformation class that can [encode] an instance of [DocumentCreateConfidentialityEnum] to String,
/// and [decode] dynamic data back to [DocumentCreateConfidentialityEnum].
class DocumentCreateConfidentialityEnumTypeTransformer {
  factory DocumentCreateConfidentialityEnumTypeTransformer() => _instance ??= const DocumentCreateConfidentialityEnumTypeTransformer._();

  const DocumentCreateConfidentialityEnumTypeTransformer._();

  String encode(DocumentCreateConfidentialityEnum data) => data.value;

  /// Decodes a [dynamic value][data] to a DocumentCreateConfidentialityEnum.
  ///
  /// If [allowNull] is true and the [dynamic value][data] cannot be decoded successfully,
  /// then null is returned. However, if [allowNull] is false and the [dynamic value][data]
  /// cannot be decoded successfully, then an [UnimplementedError] is thrown.
  ///
  /// The [allowNull] is very handy when an API changes and a new enum value is added or removed,
  /// and users are still using an old app with the old code.
  DocumentCreateConfidentialityEnum? decode(dynamic data, {bool allowNull = true}) {
    if (data != null) {
      switch (data) {
        case r'pubblico': return DocumentCreateConfidentialityEnum.pubblico;
        case r'interno': return DocumentCreateConfidentialityEnum.interno;
        case r'riservato': return DocumentCreateConfidentialityEnum.riservato;
        default:
          if (!allowNull) {
            throw ArgumentError('Unknown enum value to decode: $data');
          }
      }
    }
    return null;
  }

  /// Singleton [DocumentCreateConfidentialityEnumTypeTransformer] instance.
  static DocumentCreateConfidentialityEnumTypeTransformer? _instance;
}


