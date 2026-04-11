import csv
import io
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError

from library.models import KnowledgeNode
from ..models import Question, QuestionOption
from ..serializers import QuestionManagerSerializer

class BulkCSVUploadView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        if 'file' not in request.FILES:
            return Response({"error": "No CSV file uploaded."}, status=status.HTTP_400_BAD_REQUEST)

        csv_file = request.FILES['file']
        if not csv_file.name.endswith('.csv'):
            return Response({"error": "File must be a CSV."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            decoded_file = csv_file.read().decode('utf-8-sig')
            io_string = io.StringIO(decoded_file)
            reader = csv.DictReader(io_string)
        except Exception:
            return Response({"error": "Invalid CSV encoding. Use UTF-8."}, status=status.HTTP_400_BAD_REQUEST)

        required_columns = [
            'topic_id', 'question_text', 'question_type', 'difficulty', 
            'positive_marks', 'negative_marks', 'explanation'
        ]
        
        if not all(col in reader.fieldnames for col in required_columns):
            return Response({
                "error": f"Missing required columns. Expected at least: {', '.join(required_columns)}"
            }, status=status.HTTP_400_BAD_REQUEST)

        created_questions_count = 0
        row_num = 1
        topic_cache = {}

        try:
            with transaction.atomic():
                for row in reader:
                    row_num += 1
                    
                    topic_id = row.get('topic_id', '').strip()
                    topic = None
                    if topic_id:
                        if topic_id not in topic_cache:
                            try:
                                topic_cache[topic_id] = KnowledgeNode.objects.filter(id=topic_id).first()
                            except ValidationError:
                                raise ValueError(f"Row {row_num}: Invalid UUID format for topic_id.")
                        topic = topic_cache[topic_id]
                    
                    try:
                        p_raw = row.get('positive_marks', '').strip()
                        n_raw = row.get('negative_marks', '').strip()
                        p_marks = float(p_raw) if p_raw else 1.0
                        n_marks = float(n_raw) if n_raw else 0.0
                    except ValueError:
                        raise ValueError(f"Row {row_num}: Marks must be numeric decimals.")

                    question = Question.objects.create(
                        topic=topic,
                        question_type=row.get('question_type', 'SINGLE').strip().upper(),
                        text=row.get('question_text', '').strip(),
                        explanation=row.get('explanation', '').strip(),
                        difficulty=row.get('difficulty', 'MEDIUM').strip().upper(),
                        positive_marks=p_marks,
                        negative_marks=n_marks
                    )

                    options_to_create = []
                    for i in range(1, 7): 
                        opt_text_key = f'opt{i}_text'
                        opt_correct_key = f'opt{i}_correct'
                        
                        if opt_text_key in row and row[opt_text_key].strip():
                            is_correct = str(row.get(opt_correct_key, '')).strip().lower() in ['true', '1', 'yes']
                            options_to_create.append(QuestionOption(
                                question=question,
                                text=row[opt_text_key].strip(),
                                is_correct=is_correct
                            ))
                    
                    if not options_to_create:
                        raise ValueError(f"Row {row_num}: Question must have at least one option.")
                        
                    QuestionOption.objects.bulk_create(options_to_create)
                    created_questions_count += 1

        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": f"Database error on row {row_num}: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            "message": f"Successfully imported {created_questions_count} questions."
        }, status=status.HTTP_201_CREATED)


class AdminQuestionBankView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        questions = Question.objects.prefetch_related('options').all().order_by('-created_at')[:200]
        return Response(QuestionManagerSerializer(questions, many=True).data, status=status.HTTP_200_OK)