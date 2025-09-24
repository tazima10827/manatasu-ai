import 'dart:typed_data';
import 'dart:math' as math;
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
  String? _extractedText;

  bool get isLoading => _isLoading;
  PlatformFile? get uploadedPDF => _uploadedPDF;
  ProblemGenerationParams? get params => _params;
  List<GeneratedProblem> get generatedProblems => _generatedProblems;
  String? get errorMessage => _errorMessage;
  Uint8List? get generatedPdfBytes => _generatedPdfBytes;
  String? get extractedText => _extractedText;

  final ApiService _apiService = ApiService();

  Future<Uint8List> _generateBlankPDF() async {
    final pdf = pw.Document();
    pdf.addPage(
      pw.Page(
        pageFormat: PdfPageFormat.a4,
        build: (pw.Context context) {
          return pw.Center(
            child: pw.Text(
              '',
              style: const pw.TextStyle(fontSize: 12),
            ),
          );
        },
      ),
    );
    return await pdf.save();
  }

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
    if (_params == null) {
      _errorMessage = 'パラメータを設定してください';
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
        if (_uploadedPDF != null) {
          // PDFがアップロードされている場合
          final result = await _apiService.generateProblems(
            pdfBytes: _uploadedPDF!.bytes!,
            params: _params!,
          );
          _generatedProblems = result.problems;
          _extractedText = result.extractedText;
        } else {
          // PDFがない場合は白紙のPDFを送信
          final blankPdfBytes = await _generateBlankPDF();
          final result = await _apiService.generateProblems(
            pdfBytes: blankPdfBytes,
            params: _params!,
          );
          _generatedProblems = result.problems;
          _extractedText = result.extractedText;
        }
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
        final pdfBytes = additionalPDF?.bytes ?? _uploadedPDF?.bytes ?? await _generateBlankPDF();
        final result = await _apiService.generateProblems(
          pdfBytes: pdfBytes,
          params: params,
        );
        newProblems = result.problems;
        // 追加生成でも抽出テキストを更新
        if (result.extractedText != null) {
          _extractedText = result.extractedText;
        }
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

    // 問題を複数ページに効率的に配置
    const int problemsPerPage = 3; // 1ページに最大3問
    final int totalPages = (_generatedProblems.length / problemsPerPage).ceil();

    for (int pageIndex = 0; pageIndex < totalPages; pageIndex++) {
      final startIndex = pageIndex * problemsPerPage;
      final endIndex = math.min(startIndex + problemsPerPage, _generatedProblems.length);
      final problemsOnThisPage = _generatedProblems.sublist(startIndex, endIndex);

      pdf.addPage(
        pw.Page(
          pageFormat: PdfPageFormat.a4,
          margin: const pw.EdgeInsets.all(30),
          theme: pw.ThemeData.withFont(
            base: font,
            bold: fontBold,
          ),
          build: (pw.Context context) {
            return pw.Column(
              crossAxisAlignment: pw.CrossAxisAlignment.start,
              children: [
                // ページヘッダー
                pw.Container(
                  width: double.infinity,
                  padding: const pw.EdgeInsets.symmetric(vertical: 8, horizontal: 12),
                  decoration: pw.BoxDecoration(
                    color: PdfColors.blue50,
                    borderRadius: const pw.BorderRadius.all(pw.Radius.circular(5)),
                    border: pw.Border.all(width: 1, color: PdfColors.blue200),
                  ),
                  child: pw.Text(
                    convertJapaneseForWeb('問題集 - ${pageIndex + 1}ページ目'),
                    style: pw.TextStyle(
                      fontSize: 14,
                      fontWeight: pw.FontWeight.bold,
                      color: PdfColors.blue800,
                    ),
                    textAlign: pw.TextAlign.center,
                  ),
                ),
                pw.SizedBox(height: 20),

                // このページの問題たち
                pw.Expanded(
                  child: pw.Column(
                    children: problemsOnThisPage.asMap().entries.map((entry) {
                      final localIndex = entry.key;
                      final globalIndex = startIndex + localIndex;
                      final problem = entry.value;
                      final isLastOnPage = localIndex == problemsOnThisPage.length - 1;

                      return pw.Container(
                        margin: pw.EdgeInsets.only(bottom: isLastOnPage ? 0 : 15),
                        child: pw.Column(
                          crossAxisAlignment: pw.CrossAxisAlignment.start,
                          children: [
                            // 問題番号と問題文をコンパクトに
                            pw.Container(
                              width: double.infinity,
                              padding: const pw.EdgeInsets.symmetric(vertical: 6, horizontal: 12),
                              decoration: pw.BoxDecoration(
                                color: PdfColors.grey100,
                                borderRadius: const pw.BorderRadius.all(pw.Radius.circular(4)),
                                border: pw.Border.all(width: 0.5, color: PdfColors.grey300),
                              ),
                              child: pw.Text(
                                convertJapaneseForWeb('問題 ${globalIndex + 1}'),
                                style: pw.TextStyle(
                                  fontSize: 13,
                                  fontWeight: pw.FontWeight.bold,
                                ),
                              ),
                            ),
                            pw.SizedBox(height: 8),

                            // 問題文
                            pw.Padding(
                              padding: const pw.EdgeInsets.only(left: 8),
                              child: pw.Text(
                                convertJapaneseForWeb(problem.question),
                                style: const pw.TextStyle(fontSize: 12, lineSpacing: 1.3),
                              ),
                            ),
                            pw.SizedBox(height: 8),

                            // 選択肢（ある場合）- コンパクト表示
                            if (problem.choices != null && problem.choices!.isNotEmpty) ...[
                              pw.Padding(
                                padding: const pw.EdgeInsets.only(left: 8),
                                child: pw.Wrap(
                                  spacing: 15,
                                  runSpacing: 3,
                                  children: problem.choices!.asMap().entries.map((choiceEntry) {
                                    return pw.Text(
                                      '${choiceEntry.key + 1}. ${convertJapaneseForWeb(choiceEntry.value)}',
                                      style: const pw.TextStyle(fontSize: 11),
                                    );
                                  }).toList(),
                                ),
                              ),
                              pw.SizedBox(height: 8),
                            ],

                            // コンパクトな解答欄
                            pw.Container(
                              width: double.infinity,
                              height: 30,
                              margin: const pw.EdgeInsets.only(left: 8),
                              decoration: pw.BoxDecoration(
                                border: pw.Border.all(width: 1, color: PdfColors.grey400),
                                borderRadius: const pw.BorderRadius.all(pw.Radius.circular(3)),
                              ),
                              child: pw.Padding(
                                padding: const pw.EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                child: pw.Align(
                                  alignment: pw.Alignment.centerLeft,
                                  child: pw.Text(
                                    convertJapaneseForWeb('解答: '),
                                    style: pw.TextStyle(
                                      fontSize: 10,
                                      color: PdfColors.grey600,
                                    ),
                                  ),
                                ),
                              ),
                            ),

                            if (!isLastOnPage) pw.SizedBox(height: 15),
                          ],
                        ),
                      );
                    }).toList(),
                  ),
                ),

                pw.SizedBox(height: 15),

                // ページフッター（ページ番号のみ）
                pw.Container(
                  width: double.infinity,
                  padding: const pw.EdgeInsets.all(8),
                  decoration: pw.BoxDecoration(
                    color: PdfColors.grey50,
                    border: pw.Border.all(width: 0.5, color: PdfColors.grey300),
                    borderRadius: const pw.BorderRadius.all(pw.Radius.circular(3)),
                  ),
                  child: pw.Text(
                    convertJapaneseForWeb('ページ ${pageIndex + 1} / $totalPages'),
                    style: pw.TextStyle(fontSize: 8, color: PdfColors.grey600),
                    textAlign: pw.TextAlign.center,
                  ),
                ),
              ],
            );
          },
        ),
      );
    }

    // 解答・解説ページを別途追加
    if (_generatedProblems.isNotEmpty) {
      pdf.addPage(
        pw.MultiPage(
          pageFormat: PdfPageFormat.a4,
          margin: const pw.EdgeInsets.all(30),
          theme: pw.ThemeData.withFont(
            base: font,
            bold: fontBold,
          ),
          build: (pw.Context context) {
            return [
              pw.Container(
                width: double.infinity,
                padding: const pw.EdgeInsets.symmetric(vertical: 12, horizontal: 20),
                decoration: pw.BoxDecoration(
                  color: PdfColors.blue100,
                  borderRadius: const pw.BorderRadius.all(pw.Radius.circular(8)),
                ),
                child: pw.Text(
                  convertJapaneseForWeb('解答・解説'),
                  style: pw.TextStyle(
                    fontSize: 18,
                    fontWeight: pw.FontWeight.bold,
                  ),
                  textAlign: pw.TextAlign.center,
                ),
              ),
              pw.SizedBox(height: 20),

              // 各問題の解答・解説をコンパクトに
              for (var i = 0; i < _generatedProblems.length; i++) ...[
                pw.Container(
                  width: double.infinity,
                  margin: const pw.EdgeInsets.only(bottom: 15),
                  decoration: pw.BoxDecoration(
                    border: pw.Border.all(width: 1, color: PdfColors.grey300),
                    borderRadius: const pw.BorderRadius.all(pw.Radius.circular(5)),
                  ),
                  child: pw.Column(
                    crossAxisAlignment: pw.CrossAxisAlignment.start,
                    children: [
                      pw.Container(
                        width: double.infinity,
                        padding: const pw.EdgeInsets.symmetric(vertical: 6, horizontal: 12),
                        decoration: const pw.BoxDecoration(
                          color: PdfColors.grey100,
                          borderRadius: pw.BorderRadius.only(
                            topLeft: pw.Radius.circular(4),
                            topRight: pw.Radius.circular(4),
                          ),
                        ),
                        child: pw.Text(
                          convertJapaneseForWeb('問題 ${i + 1}'),
                          style: pw.TextStyle(
                            fontSize: 12,
                            fontWeight: pw.FontWeight.bold,
                          ),
                        ),
                      ),
                      pw.Padding(
                        padding: const pw.EdgeInsets.all(12),
                        child: pw.Column(
                          crossAxisAlignment: pw.CrossAxisAlignment.start,
                          children: [
                            pw.Text(
                              convertJapaneseForWeb('正解: ${_generatedProblems[i].answer}'),
                              style: pw.TextStyle(
                                fontWeight: pw.FontWeight.bold,
                                fontSize: 11,
                                color: PdfColors.red600,
                              ),
                            ),
                            pw.SizedBox(height: 5),
                            pw.Text(
                              convertJapaneseForWeb('解説: ${_generatedProblems[i].explanation}'),
                              style: const pw.TextStyle(fontSize: 10, lineSpacing: 1.3),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ];
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