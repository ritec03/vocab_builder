// app/user/[userId]/lesson/page.tsx
'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import axios from 'axios';
import TaskCard from '../../../ui/components/TaskCard';
import ScoreCard from '../../../ui/components/ScoreCard';
import Header from '../../../ui/components/Header';
import { Task } from '@/app/lib/definitions';

interface LessonHead {
    lesson_id: number;
    task: {
        order: [number, number];
        first_task: Task;
    };
}

interface SubmitTaskResponse {
    score: Record<number, number>[]
    next_task: {
        order: [number, number]
        task: Task
    } | null 
}

const LessonPage: React.FC = () => {
    const params = useParams();
    const userId = params.userId as string;
    const router = useRouter();
    const [lesson, setLesson] = useState<LessonHead | null>(null);
    const [currentTask, setCurrentTask] = useState<{task: Task, order: [number,number]} | null>(null);
    const [score, setScore] = useState<any>(null);
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(true);
    const [checking, setChecking] = useState(false);

    useEffect(() => {
        const fetchLesson = async () => {
            try {
                const response: {data: LessonHead} = await axios.post(`${process.env.NEXT_PUBLIC_API_URL}/users/${userId}/lessons`);
                setLesson(response.data);
                setCurrentTask({task:response.data.task.first_task, order: response.data.task.order});
                setLoading(false);
            } catch (error) {
                setError('Failed to fetch lesson.');
                setLoading(false);
            }
        };

        fetchLesson();
    }, [userId]);

    const handleTaskSubmit = async (answer: string) => {
        if (lesson && currentTask) {
            setChecking(true);
            try {
                const response: {data: SubmitTaskResponse} = await axios.post(`${process.env.NEXT_PUBLIC_API_URL}/users/${userId}/lessons/${lesson.lesson_id}/tasks/submit`, {
                    task_id: currentTask.task.id,
                    task_order: currentTask.order,
                    answer
                });
                setScore(response.data.score);
                setCurrentTask(response.data.next_task ? response.data.next_task : null);
                setChecking(false);
            } catch (error) {
                setError('Failed to submit task.');
                setChecking(false);
            }
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
            {error && <p className="text-red-500">{error}</p>}
            {loading ? (
                <p>Loading lesson...</p>
            ) : checking ? (
                <p>Checking your answer...</p>
            ) : score ? (
                <ScoreCard score={score} onContinue={handleContinue} onFinishLesson={handleFinishLesson} />
            ) : currentTask ? (
                <TaskCard task={currentTask.task} onSubmit={handleTaskSubmit} />
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
            )}
        </main>
    );
};

export default LessonPage;


// TODOs
// # save generated tasks to a file for db prepopulation