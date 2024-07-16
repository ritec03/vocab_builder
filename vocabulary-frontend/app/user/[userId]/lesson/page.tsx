// app/user/[userId]/lesson/page.tsx
'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import axios from 'axios';
import TaskCard from '../../../ui/components/TaskCard';
import ScoreCard from '../../../ui/components/ScoreCard';
import Header from '../../../ui/components/Header';

interface Task {
    id: number;
    task_string: string;
    template: {
        id: number;
        template: string;
        task_type: string;
        starting_language: string;
        target_language: string;
    };
    correctAnswer: string;
    resources: {
        id: number;
        resource: string;
        target_words: {
            id: number;
            item: string;
            pos: string;
            freq: number;
        }[];
    }[];
    learning_items: {
        id: number;
        item: string;
        pos: string;
        freq: number;
    }[];
}

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
// TODOs
// # erase the form after completion???
// # somehow indicate that the task is being loaded?
// # Handle logic of conitnue button on Score card
// # show score card after each task??

const LessonPage: React.FC = () => {
    const params = useParams();
    const userId = params.userId as string;
    const router = useRouter();
    const [lesson, setLesson] = useState<LessonHead | null>(null);
    const [currentTask, setCurrentTask] = useState<{task: Task, order: [number,number]} | null>(null);
    const [score, setScore] = useState<any>(null);
    const [error, setError] = useState('');

    useEffect(() => {
        const fetchLesson = async () => {
            try {
                const response: {data: LessonHead} = await axios.post(`${process.env.NEXT_PUBLIC_API_URL}/users/${userId}/lessons`);
                setLesson(response.data);
                setCurrentTask({task:response.data.task.first_task, order: response.data.task.order});
            } catch (error) {
                setError('Failed to fetch lesson.');
            }
        };

        fetchLesson();
    }, [userId]);

    const handleTaskSubmit = async (answer: string) => {
        if (lesson && currentTask) {
            try {
                const response: {data: SubmitTaskResponse} = await axios.post(`${process.env.NEXT_PUBLIC_API_URL}/users/${userId}/lessons/${lesson.lesson_id}/tasks/submit`, {
                    task_id: currentTask.task.id,
                    task_order: currentTask.order,
                    answer
                });
                setScore(response.data.score);
                setCurrentTask(response.data.next_task ? response.data.next_task : null);
            } catch (error) {
                setError('Failed to submit task.');
            }
        }
    };

    const handleFinishLesson = () => {
        router.push(`/user/${userId}`);
    };

    return (
        <main className="flex min-h-screen flex-col items-center justify-center p-24">
            <Header />
            {error && <p className="text-red-500">{error}</p>}
            {currentTask ? (
                <TaskCard task={currentTask.task} onSubmit={handleTaskSubmit} />
            ) : score ? (
                <ScoreCard score={score} onContinue={() => setScore(null)} onFinishLesson={handleFinishLesson} />
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
