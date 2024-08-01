// app/user/[userId]/lesson/page.tsx
'use client';

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import TaskCard from '../../../ui/components/TaskCard';
import FourChoiceTaskCard from '../../../ui/components/FourChoiceTaskCard';
import ScoreCard from '../../../ui/components/ScoreCard';
import Header from '../../../ui/components/Header';
import { Score, Task } from '@/app/lib/definitions';

interface Order {
    sequence_num: number;
    attempt: number;
}

interface OrderedTask {
    order: Order;
    task: Task;
}

interface LessonHead {
    lesson_id: number;
    first_task: OrderedTask;
}

interface SubmitTaskResponse {
    score: Score[];
    next_task: OrderedTask | null ;
    final_score?: Score[];
}

interface SubmitTask {
    userId: string;
    lessonId: number;
    taskId: number;
    order: Order;
    answer: string;
}

const fetchLesson = async (userId: string): Promise<LessonHead> => {
    const response = await axios.get(`${process.env.NEXT_PUBLIC_API_URL}/users/${userId}/lessons`);
    return response.data;
};

const submitTask = async ({ userId, lessonId, taskId, order, answer }: SubmitTask) => {
    const response = await axios.post(`${process.env.NEXT_PUBLIC_API_URL}/users/${userId}/lessons/${lessonId}/tasks/submit`, {
        task_id: taskId,
        task_order: order,
        answer
    });
    return response.data;
};

const LessonPage: React.FC = () => {
    const params = useParams();
    const userId = params.userId as string;
    const router = useRouter();

    const [currentTask, setCurrentTask] = useState<OrderedTask | null>(null);
    const [score, setScore] = useState<Score[] | null>(null);

    const { data: lesson, error, isLoading, isError, isSuccess } = useQuery<LessonHead>(
        {queryKey: ['lesson', userId],
        queryFn: async () => {
                const data = await fetchLesson(userId);
                setCurrentTask(data.first_task);
                return data;
            },
        }, 
    );

    const mutationSubmitTask = useMutation({
        mutationFn: async ({ userId, lessonId, taskId, order, answer }: SubmitTask) => {
            return await submitTask({ userId, lessonId, taskId, order, answer });
        },
        onSuccess: (data: SubmitTaskResponse) => {
            setScore(data.score);
            setCurrentTask(data.next_task || null);
        },
    });        
        
    const handleTaskSubmit = async (answer: string) => {
        if (lesson && currentTask) {
            mutationSubmitTask.mutate(
                { 
                    userId, 
                    lessonId: lesson.lesson_id, 
                    taskId: currentTask.task.id, 
                    order: currentTask.order, 
                    answer 
                });
        }
    };

    const handleFinishLesson = () => {
        router.push(`/user/${userId}`);
    };

    const handleContinue = () => {
        setScore(null);
    };

    return (
        <main className="flex min-h-screen flex-col items-center justify-center p-24">
            <Header />
            {(isLoading) ? (
                // BUG fix loading screen - it does not show up
                <p>Just a moment. Loading your lesson...</p>
            ) : (isError) ? (
                <p className="text-red-500">Failed to fetch lesson.</p>
            ) : ((isSuccess)) ? (
                mutationSubmitTask.isPending ? (
                    <p>Submitting your answer...</p>
                ) : score ? (
                    <ScoreCard hasNextTask={currentTask !== null} score={score} onContinue={handleContinue} onFinishLesson={handleFinishLesson} />
                ) : currentTask ? (
                    currentTask.task.task_type === 'FOUR_CHOICE' ? (
                        <FourChoiceTaskCard task={currentTask.task} onSubmit={handleTaskSubmit} />
                    ) : (
                        <TaskCard task={currentTask.task} onSubmit={handleTaskSubmit} />
                    )
                ) : (
                    <div className="text-center">
                        <p>No more tasks available.</p>
                        <button
                            onClick={handleFinishLesson}
                            className="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline mt-4"
                        >
                            Finish Lesson
                        </button>
                    </div>
                )
            ) : (
                <p>Something went wrong.</p>
            )
            
            }
        </main>
    );
};

export default LessonPage;