import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:file_picker/file_picker.dart';
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;
import 'package:printing/printing.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:http/http.dart' as http;
import '../models/problem_generation_params.dart';
import '../models/generated_problem.dart';
import '../services/api_service.dart';
import '../utils/config.dart';

class ProblemGeneratorProvider extends ChangeNotifier {
  bool _isLoading = false;
  PlatformFile? _uploadedPDF;
  ProblemGenerationParams? _params;
  List<GeneratedProblem> _generatedProblems = [];
  String? _errorMessage;
  Uint8List? _generatedPdfBytes;

  bool get isLoading => _isLoading;
  PlatformFile? get uploadedPDF => _uploadedPDF;
  ProblemGenerationParams? get params => _params;
  List<GeneratedProblem> get generatedProblems => _generatedProblems;
  String? get errorMessage => _errorMessage;
  Uint8List? get generatedPdfBytes => _generatedPdfBytes;

  final ApiService _apiService = ApiService();

  Future<void> uploadPDF() async {
    try {
      FilePickerResult? result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['pdf'],
        allowMultiple: false,
      );

      if (result != null) {
        _uploadedPDF = result.files.first;
        _errorMessage = null;
        notifyListeners();
      }
    } catch (e) {
      _errorMessage = 'PDFのアップロードに失敗しました: $e';
      notifyListeners();
    }
  }

  void clearUploadedPDF() {
    _uploadedPDF = null;
    notifyListeners();
  }

  void setParams(ProblemGenerationParams params) {
    _params = params;
    notifyListeners();
  }

  Future<void> generateProblems() async {
    if (_uploadedPDF == null || _params == null) {
      _errorMessage = 'PDFとパラメータを設定してください';
      notifyListeners();
      return;
    }

    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      if (Config.useMockData) {
        await Future.delayed(const Duration(seconds: 2));
        _generatedProblems = ApiService.getMockProblems(_params!);
      } else {
        _generatedProblems = await _apiService.generateProblems(
          pdfBytes: _uploadedPDF!.bytes!,
          params: _params!,
        );
      }

      await _generatePDF();

      _isLoading = false;
      notifyListeners();
    } catch (e) {
      _errorMessage = '問題生成に失敗しました: $e';
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> addMoreProblems({
    PlatformFile? additionalPDF,
    required ProblemGenerationParams params,
  }) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      List<GeneratedProblem> newProblems;

      if (Config.useMockData) {
        await Future.delayed(const Duration(seconds: 2));
        newProblems = ApiService.getMockProblems(params);
        // 既存の問題と重複しないようにIDを調整
        final startIndex = _generatedProblems.length;
        for (int i = 0; i < newProblems.length; i++) {
          newProblems[i] = GeneratedProblem(
            id: 'problem_${startIndex + i + 1}',
            question: newProblems[i].question.replaceAll('問題 ${i + 1}', '問題 ${startIndex + i + 1}'),
            answer: newProblems[i].answer,
            explanation: newProblems[i].explanation,
            choices: newProblems[i].choices,
            difficulty: newProblems[i].difficulty,
            subject: newProblems[i].subject,
            grade: newProblems[i].grade,
            sourceFile: additionalPDF?.name ?? _uploadedPDF?.name ?? 'sample.pdf',
            sourcePage: newProblems[i].sourcePage,
            sourceUri: newProblems[i].sourceUri,
            generatedAt: newProblems[i].generatedAt,
          );
        }
      } else {
        final pdfBytes = additionalPDF?.bytes ?? _uploadedPDF!.bytes!;
        newProblems = await _apiService.generateProblems(
          pdfBytes: pdfBytes,
          params: params,
        );
      }

      _generatedProblems.addAll(newProblems);
      await _generatePDF();

      _isLoading = false;
      notifyListeners();
    } catch (e) {
      _errorMessage = '追加問題の生成に失敗しました: $e';
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> _generatePDF() async {
    final pdf = pw.Document();

    // ShipporiMincho-Bold.ttfを使用
    pw.Font font;
    pw.Font fontBold;

    // デフォルトフォントで初期化
    font = pw.Font.helvetica();
    fontBold = pw.Font.helveticaBold();

    // Webとモバイルの両方でShipporiMincho-Bold.ttfを使用
    try {
      final fontData = await rootBundle.load('assets/fonts/ShipporiMincho-Bold.ttf');
      // 正しいByteData変換を使用
      final fontBytes = fontData.buffer.asUint8List();
      final byteData = ByteData.sublistView(fontBytes);
      font = pw.Font.ttf(byteData);
      fontBold = pw.Font.ttf(byteData);
      print('ShipporiMincho-Bold.ttf font loaded successfully');
    } catch (e) {
      print('Font loading error: $e');
      // フォント読み込みに失敗した場合のフォールバック（既に設定済み）
    }

    // Web環境での日本語文字変換関数
    String convertJapaneseForWeb(String text) {
      // 英語変換を無効化して日本語をそのまま返す
      return text;
    }

    for (var i = 0; i < _generatedProblems.length; i++) {
      final problem = _generatedProblems[i];

      pdf.addPage(
        pw.Page(
          pageFormat: PdfPageFormat.a4,
          theme: pw.ThemeData.withFont(
            base: font,
            bold: fontBold,
          ),
          build: (pw.Context context) {
            return pw.Column(
              crossAxisAlignment: pw.CrossAxisAlignment.start,
              children: [
                pw.Text(
                  convertJapaneseForWeb('問題 ${i + 1}'),
                  style: pw.TextStyle(
                    fontSize: 18,
                    fontWeight: pw.FontWeight.bold,
                  ),
                ),
                pw.SizedBox(height: 10),
                pw.Text(
                  convertJapaneseForWeb(problem.question),
                  style: const pw.TextStyle(fontSize: 14),
                ),
                pw.SizedBox(height: 20),
                if (problem.choices != null && problem.choices!.isNotEmpty) ...[
                  pw.Text(
                    convertJapaneseForWeb('選択肢:'),
                    style: pw.TextStyle(fontWeight: pw.FontWeight.bold),
                  ),
                  pw.SizedBox(height: 5),
                  ...problem.choices!.asMap().entries.map((entry) {
                    return pw.Padding(
                      padding: const pw.EdgeInsets.only(left: 20, top: 5),
                      child: pw.Text('${entry.key + 1}. ${convertJapaneseForWeb(entry.value)}'),
                    );
                  }).toList(),
                  pw.SizedBox(height: 20),
                ],
                pw.Text(
                  convertJapaneseForWeb('解答: ${problem.answer}'),
                  style: pw.TextStyle(fontWeight: pw.FontWeight.bold),
                ),
                pw.SizedBox(height: 10),
                pw.Text(
                  convertJapaneseForWeb('解説: ${problem.explanation}'),
                  style: const pw.TextStyle(fontSize: 12),
                ),
                pw.SizedBox(height: 20),
                pw.Container(
                  padding: const pw.EdgeInsets.all(10),
                  decoration: pw.BoxDecoration(
                    border: pw.Border.all(width: 1),
                    borderRadius: const pw.BorderRadius.all(pw.Radius.circular(5)),
                  ),
                  child: pw.Column(
                    crossAxisAlignment: pw.CrossAxisAlignment.start,
                    children: [
                      pw.Text(
                        convertJapaneseForWeb('出典情報'),
                        style: pw.TextStyle(fontWeight: pw.FontWeight.bold),
                      ),
                      pw.SizedBox(height: 5),
                      pw.Text(convertJapaneseForWeb('ファイル: ${problem.sourceFile}')),
                      pw.Text(convertJapaneseForWeb('ページ: ${problem.sourcePage}')),
                      if (problem.sourceUri != null)
                        pw.Text('URI: ${problem.sourceUri}'),
                    ],
                  ),
                ),
              ],
            );
          },
        ),
      );
    }

    _generatedPdfBytes = await pdf.save();
  }

  void removeProblem(int index) {
    if (index >= 0 && index < _generatedProblems.length) {
      _generatedProblems.removeAt(index);
      notifyListeners();
    }
  }

  void reorderProblems(int oldIndex, int newIndex) {
    if (oldIndex < newIndex) {
      newIndex -= 1;
    }
    final item = _generatedProblems.removeAt(oldIndex);
    _generatedProblems.insert(newIndex, item);
    notifyListeners();
  }

  void reset() {
    _isLoading = false;
    _uploadedPDF = null;
    _params = null;
    _generatedProblems = [];
    _errorMessage = null;
    _generatedPdfBytes = null;
    notifyListeners();
  }

  void clearForNewGeneration() {
    _isLoading = false;
    _uploadedPDF = null;
    _params = null;
    _errorMessage = null;
    _generatedPdfBytes = null;
    notifyListeners();
  }
}