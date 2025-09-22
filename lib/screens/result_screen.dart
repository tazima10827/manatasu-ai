import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:go_router/go_router.dart';
import 'package:printing/printing.dart';
import 'dart:html' as html;
import 'dart:typed_data';
import '../providers/problem_generator_provider.dart';
import '../widgets/add_more_problems_dialog.dart';

class ResultScreen extends StatefulWidget {
  const ResultScreen({super.key});

  @override
  State<ResultScreen> createState() => _ResultScreenState();
}

class _ResultScreenState extends State<ResultScreen> {
  bool _showPreview = false;

  void _downloadPdf(Uint8List pdfBytes) {
    final blob = html.Blob([pdfBytes]);
    final url = html.Url.createObjectUrlFromBlob(blob);
    final anchor = html.document.createElement('a') as html.AnchorElement
      ..href = url
      ..style.display = 'none'
      ..download = 'generated_problems_${DateTime.now().millisecondsSinceEpoch}.pdf';
    html.document.body!.children.add(anchor);
    anchor.click();
    html.document.body!.children.remove(anchor);
    html.Url.revokeObjectUrl(url);
  }

  void _printPdf(Uint8List pdfBytes) {
    final blob = html.Blob([pdfBytes], 'application/pdf');
    final url = html.Url.createObjectUrlFromBlob(blob);
    html.window.open(url, '_blank');
    Future.delayed(const Duration(seconds: 1), () {
      html.Url.revokeObjectUrl(url);
    });
  }

  @override
  Widget build(BuildContext context) {
    final provider = Provider.of<ProblemGeneratorProvider>(context);

    if (provider.generatedProblems.isEmpty) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        context.go('/');
      });
      return const SizedBox.shrink();
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('生成結果'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () {
            context.go('/generate');
          },
        ),
        actions: [
          IconButton(
            icon: Icon(_showPreview ? Icons.list : Icons.preview),
            onPressed: () {
              setState(() {
                _showPreview = !_showPreview;
              });
            },
            tooltip: _showPreview ? 'リスト表示' : 'プレビュー表示',
          ),
          IconButton(
            icon: const Icon(Icons.print),
            onPressed: provider.generatedPdfBytes != null
                ? () => _printPdf(provider.generatedPdfBytes!)
                : null,
            tooltip: '印刷',
          ),
          IconButton(
            icon: const Icon(Icons.download),
            onPressed: provider.generatedPdfBytes != null
                ? () => _downloadPdf(provider.generatedPdfBytes!)
                : null,
            tooltip: 'ダウンロード',
          ),
          const SizedBox(width: 16),
        ],
      ),
      body: Column(
        children: [
          Container(
            padding: const EdgeInsets.all(16),
            color: Theme.of(context).colorScheme.primaryContainer.withOpacity(0.3),
            child: Row(
              children: [
                const Icon(Icons.check_circle, color: Colors.green),
                const SizedBox(width: 8),
                Text(
                  '${provider.generatedProblems.length}問の問題が生成されました',
                  style: const TextStyle(fontWeight: FontWeight.bold),
                ),
                const Spacer(),
                OutlinedButton.icon(
                  onPressed: () {
                    showDialog(
                      context: context,
                      builder: (context) => const AddMoreProblemsDialog(),
                    );
                  },
                  icon: const Icon(Icons.add_circle_outline),
                  label: const Text('問題を追加'),
                ),
                const SizedBox(width: 12),
                ElevatedButton.icon(
                  onPressed: () {
                    provider.reset();
                    context.go('/');
                  },
                  icon: const Icon(Icons.refresh),
                  label: const Text('新しく作成'),
                ),
              ],
            ),
          ),
          Expanded(
            child: _showPreview && provider.generatedPdfBytes != null
                ? PdfPreview(
                    build: (format) => provider.generatedPdfBytes!,
                    allowSharing: false,
                    allowPrinting: false,
                    canChangePageFormat: false,
                    canChangeOrientation: false,
                    canDebug: false,
                  )
                : ReorderableListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: provider.generatedProblems.length,
                    onReorder: (oldIndex, newIndex) {
                      provider.reorderProblems(oldIndex, newIndex);
                    },
                    itemBuilder: (context, index) {
                      final problem = provider.generatedProblems[index];
                      return Card(
                        key: ValueKey(problem.id),
                        margin: const EdgeInsets.only(bottom: 16),
                        child: ExpansionTile(
                          key: ValueKey('expansion_${problem.id}'),
                          initiallyExpanded: true,
                          title: Row(
                            children: [
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Row(
                                      children: [
                                        Icon(Icons.drag_handle, color: Colors.grey[600]),
                                        const SizedBox(width: 8),
                                        Text(
                                          '問題 ${index + 1}',
                                          style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                                        ),
                                      ],
                                    ),
                                    const SizedBox(height: 8),
                                    Text(
                                      problem.question,
                                      style: const TextStyle(fontSize: 14, color: Colors.black87),
                                    ),
                                    const SizedBox(height: 8),
                                    Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                                      decoration: BoxDecoration(
                                        color: Theme.of(context).colorScheme.primaryContainer.withOpacity(0.7),
                                        borderRadius: BorderRadius.circular(16),
                                      ),
                                      child: Text(
                                        '正解: ${problem.answer}',
                                        style: TextStyle(
                                          fontSize: 13,
                                          fontWeight: FontWeight.w500,
                                          color: Theme.of(context).colorScheme.primary,
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                              IconButton(
                                icon: const Icon(Icons.close, color: Colors.red),
                                onPressed: () {
                                  showDialog(
                                    context: context,
                                    builder: (context) => AlertDialog(
                                      title: const Text('問題を削除'),
                                      content: Text('問題 ${index + 1} を削除しますか？'),
                                      actions: [
                                        TextButton(
                                          onPressed: () => Navigator.of(context).pop(),
                                          child: const Text('キャンセル'),
                                        ),
                                        TextButton(
                                          onPressed: () {
                                            provider.removeProblem(index);
                                            Navigator.of(context).pop();
                                          },
                                          child: const Text('削除', style: TextStyle(color: Colors.red)),
                                        ),
                                      ],
                                    ),
                                  );
                                },
                                tooltip: '問題を削除',
                              ),
                            ],
                          ),
                          subtitle: Padding(
                            padding: const EdgeInsets.only(top: 8),
                            child: Row(
                              children: [
                                Chip(
                                  label: Text(problem.subject),
                                  backgroundColor: Theme.of(context)
                                      .colorScheme
                                      .primaryContainer,
                                ),
                                const SizedBox(width: 8),
                                Chip(
                                  label: Text(problem.difficulty),
                                  backgroundColor: _getDifficultyColor(problem.difficulty),
                                ),
                              ],
                            ),
                          ),
                          children: [
                            Padding(
                              padding: const EdgeInsets.all(16),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  if (problem.choices != null && problem.choices!.isNotEmpty) ...[
                                    const Text(
                                      '選択肢:',
                                      style: TextStyle(fontWeight: FontWeight.bold),
                                    ),
                                    const SizedBox(height: 8),
                                    ...problem.choices!.asMap().entries.map((entry) {
                                      return Padding(
                                        padding: const EdgeInsets.only(left: 16, bottom: 4),
                                        child: Text('${entry.key + 1}. ${entry.value}'),
                                      );
                                    }).toList(),
                                    const SizedBox(height: 16),
                                  ],
                                  const Text(
                                    '解説:',
                                    style: TextStyle(fontWeight: FontWeight.bold),
                                  ),
                                  const SizedBox(height: 8),
                                  Text(problem.explanation),
                                  const SizedBox(height: 16),
                                  Container(
                                    padding: const EdgeInsets.all(12),
                                    decoration: BoxDecoration(
                                      color: Colors.grey[100],
                                      borderRadius: BorderRadius.circular(8),
                                      border: Border.all(color: Colors.grey[300]!),
                                    ),
                                    child: Row(
                                      children: [
                                        const Icon(Icons.source, size: 16),
                                        const SizedBox(width: 8),
                                        Expanded(
                                          child: Column(
                                            crossAxisAlignment: CrossAxisAlignment.start,
                                            children: [
                                              const Text(
                                                '出典情報',
                                                style: TextStyle(
                                                  fontWeight: FontWeight.bold,
                                                  fontSize: 12,
                                                ),
                                              ),
                                              const SizedBox(height: 4),
                                              Text(
                                                'ファイル: ${problem.sourceFile} | ページ: ${problem.sourcePage}',
                                                style: const TextStyle(fontSize: 11),
                                              ),
                                              if (problem.sourceUri != null)
                                                Text(
                                                  'URI: ${problem.sourceUri}',
                                                  style: const TextStyle(fontSize: 11),
                                                ),
                                            ],
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                      );
                    },
                  ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: provider.generatedPdfBytes != null
            ? () => _downloadPdf(provider.generatedPdfBytes!)
            : null,
        icon: const Icon(Icons.download),
        label: const Text('PDFをダウンロード'),
      ),
    );
  }

  Color _getDifficultyColor(String difficulty) {
    switch (difficulty) {
      case '簡単':
        return Colors.green.withOpacity(0.2);
      case '標準':
        return Colors.orange.withOpacity(0.2);
      case '難しい':
        return Colors.red.withOpacity(0.2);
      default:
        return Colors.grey.withOpacity(0.2);
    }
  }
}