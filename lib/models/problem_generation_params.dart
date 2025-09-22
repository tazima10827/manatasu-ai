class ProblemGenerationParams {
  final String subject;
  final String grade;
  final String difficulty;
  final int problemCount;
  final String problemType;
  final String? specificTopic;
  final String? additionalInstructions;

  ProblemGenerationParams({
    required this.subject,
    required this.grade,
    required this.difficulty,
    required this.problemCount,
    required this.problemType,
    this.specificTopic,
    this.additionalInstructions,
  });

  Map<String, dynamic> toJson() {
    return {
      'subject': subject,
      'grade': grade,
      'difficulty': difficulty,
      'problemCount': problemCount,
      'problemType': problemType,
      'specificTopic': specificTopic,
      'additionalInstructions': additionalInstructions,
    };
  }

  factory ProblemGenerationParams.fromJson(Map<String, dynamic> json) {
    return ProblemGenerationParams(
      subject: json['subject'] as String,
      grade: json['grade'] as String,
      difficulty: json['difficulty'] as String,
      problemCount: json['problemCount'] as int,
      problemType: json['problemType'] as String,
      specificTopic: json['specificTopic'] as String?,
      additionalInstructions: json['additionalInstructions'] as String?,
    );
  }
}