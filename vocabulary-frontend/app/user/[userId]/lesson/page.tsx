// app/user/[userId]/lesson/page.tsx
'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import axios from 'axios';
import TaskCard from '../../../ui/components/TaskCard';
import ScoreCard from '../../../ui/components/ScoreCard';
import Header from '../../../ui/components/Header';
import { LexicalItem, Score, Task } from '@/app/lib/definitions';

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

const LessonPage: React.FC = () => {
    const params = useParams();
    const userId = params.userId as string;
    const router = useRouter();
    const [lesson, setLesson] = useState<LessonHead | null>(null);
    const [currentTask, setCurrentTask] = useState<{task: Task, order: Order} | null>(null);
    const [score, setScore] = useState<Score[] | null>(null);
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(true);
    const [checking, setChecking] = useState(false);

    useEffect(() => {
        const fetchLesson = async () => {
            try {
                const response: {data: LessonHead} = await axios.post(`${process.env.NEXT_PUBLIC_API_URL}/users/${userId}/lessons`);
                setLesson(response.data);
                setCurrentTask({task:response.data.first_task.task, order: response.data.first_task.order});
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
                setCurrentTask(response.data.next_task ? response.data.next_task : null);
                setScore(response.data.score);
                setChecking(false);
            } catch (error) {
                setError('Failed to submit task.');
                setChecking(false);
            }
        }
    };

    const handleFinishLesson = () => {
        //  TODO handle finishing lesson early through the button or closing window or routing.
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
                <ScoreCard hasNextTask={currentTask !== null} score={score} onContinue={handleContinue} onFinishLesson={handleFinishLesson} />
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
