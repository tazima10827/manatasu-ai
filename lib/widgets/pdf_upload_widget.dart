import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/problem_generator_provider.dart';

class PdfUploadWidget extends StatelessWidget {
  const PdfUploadWidget({super.key});

  @override
  Widget build(BuildContext context) {
    final provider = Provider.of<ProblemGeneratorProvider>(context);

    return Container(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Container(
            height: 200,
            decoration: BoxDecoration(
              border: Border.all(
                color: Theme.of(context).colorScheme.primary.withOpacity(0.5),
                width: 2,
                style: BorderStyle.solid,
              ),
              borderRadius: BorderRadius.circular(12),
              color: Theme.of(context).colorScheme.surface,
            ),
            child: provider.uploadedPDF != null
                ? Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(
                        Icons.picture_as_pdf,
                        size: 64,
                        color: Theme.of(context).colorScheme.primary,
                      ),
                      const SizedBox(height: 16),
                      Text(
                        provider.uploadedPDF!.name,
                        style: Theme.of(context).textTheme.titleMedium,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 8),
                      Text(
                        '${(provider.uploadedPDF!.size / 1024).toStringAsFixed(2)} KB',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                      const SizedBox(height: 16),
                      TextButton.icon(
                        onPressed: () => provider.clearUploadedPDF(),
                        icon: const Icon(Icons.clear),
                        label: const Text('削除'),
                      ),
                    ],
                  )
                : InkWell(
                    onTap: () => provider.uploadPDF(),
                    borderRadius: BorderRadius.circular(12),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(
                          Icons.cloud_upload_outlined,
                          size: 64,
                          color: Theme.of(context)
                              .colorScheme
                              .primary
                              .withOpacity(0.6),
                        ),
                        const SizedBox(height: 16),
                        Text(
                          'クリックしてPDFをアップロード',
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        const SizedBox(height: 8),
                        Text(
                          'またはファイルをドラッグ＆ドロップ',
                          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                color: Colors.grey,
                              ),
                        ),
                      ],
                    ),
                  ),
          ),
          if (provider.errorMessage != null)
            Padding(
              padding: const EdgeInsets.only(top: 16),
              child: Text(
                provider.errorMessage!,
                style: TextStyle(
                  color: Theme.of(context).colorScheme.error,
                ),
              ),
            ),
          const SizedBox(height: 20),
          const Card(
            child: Padding(
              padding: EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(Icons.info_outline, size: 20),
                      SizedBox(width: 8),
                      Text(
                        'アップロードについて',
                        style: TextStyle(fontWeight: FontWeight.bold),
                      ),
                    ],
                  ),
                  SizedBox(height: 8),
                  Text(
                    '• 対応形式: PDF\n'
                    '• 最大ファイルサイズ: 50MB\n'
                    '• アップロードされたファイルは一時的に処理され、生成後に削除されます',
                    style: TextStyle(fontSize: 13),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}