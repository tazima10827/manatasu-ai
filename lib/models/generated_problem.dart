class GeneratedProblem {
  final String id;
  final String question;
  final String answer;
  final String explanation;
  final List<String>? choices;
  final String difficulty;
  final String subject;
  final String grade;
  final String sourceFile;
  final String sourcePage;
  final String? sourceUri;
  final DateTime generatedAt;

  GeneratedProblem({
    required this.id,
    required this.question,
    required this.answer,
    required this.explanation,
    this.choices,
    required this.difficulty,
    required this.subject,
    required this.grade,
    required this.sourceFile,
    required this.sourcePage,
    this.sourceUri,
    required this.generatedAt,
  });

  factory GeneratedProblem.fromJson(Map<String, dynamic> json) {
    return GeneratedProblem(
      id: json['id'] as String,
      question: json['question'] as String,
      answer: json['answer'] as String,
      explanation: json['explanation'] as String,
      choices: json['choices'] != null ? List<String>.from(json['choices']) : null,
      difficulty: json['difficulty'] as String,
      subject: json['subject'] as String,
      grade: json['grade'] as String,
      sourceFile: json['sourceFile'] as String,
      sourcePage: json['sourcePage'] as String,
      sourceUri: json['sourceUri'] as String?,
      generatedAt: DateTime.parse(json['generatedAt'] as String),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'question': question,
      'answer': answer,
      'explanation': explanation,
      'choices': choices,
      'difficulty': difficulty,
      'subject': subject,
      'grade': grade,
      'sourceFile': sourceFile,
      'sourcePage': sourcePage,
      'sourceUri': sourceUri,
      'generatedAt': generatedAt.toIso8601String(),
    };
  }
}