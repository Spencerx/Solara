import asyncio
import time
import warnings

import ipyvuetify as v
import pytest
from reacton import ipywidgets as w

import solara.tasks
from solara.server import kernel, kernel_context
from solara.tasks import TaskState, use_task
from solara.toestand import Computed
from .toestand_test import get_storage


@solara.tasks.task
def something(count: int, delay: float = 0.1):
    time.sleep(delay)
    return "42" * count


@solara.component
def ComputeButton(count, delay: float = 0.1, on_render=lambda: None):
    solara.Button("Run", on_click=lambda: something(count, delay))
    on_render()
    # print(something.result.value)
    if something.result.value:
        if something.pending:
            solara.Info("running")
        elif something.finished:
            solara.Info("Done: " + str(something.value))
        elif something.error:
            solara.Info("Error: " + str(something.exception))
        elif something.cancelled:
            solara.Info("Cancelled")
        elif something.not_called:
            solara.Info("Not called yet")
        else:
            raise RuntimeError("should not happen")


@solara.component
def Page():
    ComputeButton(2)
    ComputeButton(3)


cancel_square = False


@solara.tasks.task
def square(value: float):
    if cancel_square:
        square.cancel()
    return value**2


@solara.component
def SquareButton(value, on_render=lambda: None):
    solara.Button("Run", on_click=lambda: square(value))
    on_render()
    if square.result.value:
        if square.pending:
            solara.Info("running")
        elif square.finished:
            solara.Info("Done: " + str(square.value))
        elif square.error:
            solara.Info("Error: " + str(square.error))
        elif square.cancelled:
            solara.Info("Cancelled")
        elif square.not_called:
            solara.Info("Not called yet")
        else:
            raise RuntimeError("should not happen")


def test_task_key():
    assert "something" in get_storage(something._result).storage_key  # type: ignore
    assert "something" in get_storage(something._instance).storage_key  # type: ignore


def test_task_basic():
    results = []

    def collect():
        results.append((square._result.value._state, square.latest))

    box, rc = solara.render(SquareButton(3, on_render=collect), handle_error=False)
    button = rc.find(v.Btn, children=["Run"]).widget
    # a combination of .clear/.set is needed to force the rendering of all the states
    # otherwise some states are not rendered
    square._start_event.clear()  # type: ignore
    button.click()
    square._start_event.set()  # type: ignore
    assert square._last_finished_event  # type: ignore
    square._last_finished_event.wait()  # type: ignore
    assert results == [
        (TaskState.NOTCALLED, None),
        (TaskState.STARTING, None),
        (TaskState.RUNNING, None),
        (TaskState.FINISHED, 9),
    ]
    results.clear()
    rc.render(SquareButton(2, on_render=collect))
    button = rc.find(v.Btn, children=["Run"]).widget
    square._start_event.clear()
    button.click()
    square._start_event.set()
    square._last_finished_event.wait()  # type: ignore
    assert results == [
        # extra finished due to the rc.render call
        (TaskState.FINISHED, 9),
        (TaskState.STARTING, 9),
        (TaskState.RUNNING, 9),
        (TaskState.FINISHED, 4),
    ]


# async version

cancel_square_async = False


@solara.tasks.task
async def square_async(value: float):
    if cancel_square_async:
        square_async.cancel()
    return value**2


@solara.component
def SquareButtonAsync(value, on_render=lambda: None):
    solara.Button("Run", on_click=lambda: square_async(value))
    on_render()
    if square_async.result.value:
        if square_async.pending:
            solara.Info("running")
        elif square_async.finished:
            solara.Info("Done: " + str(square_async.value))
        elif square_async.error:
            solara.Info("Error: " + str(square_async.exception))
        elif square_async.cancelled:
            solara.Info("Cancelled")
        elif square_async.not_called:
            solara.Info("Not called yet")
        else:
            raise RuntimeError("should not happen")


@pytest.mark.asyncio
@pytest.mark.parametrize("run_in_thread", [True, False])
async def test_task_basic_async(run_in_thread):
    results = []
    assert square_async._instance.value.run_in_thread  # type: ignore
    square_async._instance.value.run_in_thread = run_in_thread  # type: ignore

    def collect():
        results.append((square_async._result.value._state, square_async.latest))

    box, rc = solara.render(SquareButtonAsync(3, on_render=collect), handle_error=False)
    button = rc.find(v.Btn, children=["Run"]).widget
    square_async._start_event.clear()  # type: ignore
    button.click()
    square_async._start_event.set()  # type: ignore
    assert square_async.current_future  # type: ignore
    await square_async.current_future  # type: ignore
    assert results == [
        (TaskState.NOTCALLED, None),
        (TaskState.STARTING, None),
        (TaskState.RUNNING, None),
        (TaskState.FINISHED, 9),
    ]
    results.clear()
    rc.render(SquareButtonAsync(2, on_render=collect))
    button = rc.find(v.Btn, children=["Run"]).widget
    square_async._start_event.clear()  # type: ignore
    button.click()
    square_async._start_event.set()  # type: ignore
    await square_async.current_future  # type: ignore
    assert results == [
        # extra finished due to the rc.render call
        (TaskState.FINISHED, 9),
        (TaskState.STARTING, 9),
        (TaskState.RUNNING, 9),
        (TaskState.FINISHED, 4),
    ]
    square_async._instance.value.run_in_thread = True  # type: ignore


def test_task_two():
    results2 = []
    results3 = []
    # ugly reset
    square._last_value = None

    def collect2():
        results2.append((square._result.value._state, square.latest))

    def collect3():
        results3.append((square._result.value._state, square.latest))

    @solara.component
    def Test():
        SquareButton(2, on_render=collect2)
        SquareButton(3, on_render=collect3)

    box, rc = solara.render(Test(), handle_error=False)
    button = rc.find(v.Btn, children=["Run"])[0].widget
    square._start_event.clear()  # type: ignore
    button.click()
    square._start_event.set()  # type: ignore
    square._last_finished_event.wait()  # type: ignore
    assert (
        results2
        == results3
        == [
            (TaskState.NOTCALLED, None),
            (TaskState.STARTING, None),
            (TaskState.RUNNING, None),
            (TaskState.FINISHED, 4),
        ]
    )
    assert len(rc.find(children=["Done: 4"])) == 2

    # now we press the second button
    results2.clear()
    results3.clear()
    button = rc.find(v.Btn, children=["Run"])[1].widget
    square._start_event.clear()  # type: ignore
    button.click()
    square._start_event.set()  # type: ignore
    assert square._last_finished_event  # type: ignore
    square._last_finished_event.wait()  # type: ignore
    assert (
        results2
        == results3
        == [
            # not a finished event, because we don't render from the start
            (TaskState.STARTING, 4),
            (TaskState.RUNNING, 4),
            (TaskState.FINISHED, 9),
        ]
    )
    assert len(rc.find(children=["Done: 9"])) == 2


def test_task_cancel_retry():
    global cancel_square
    results = []

    # ugly reset
    square._last_value = None

    def collect():
        results.append((square._result.value._state, square.value))

    box, rc = solara.render(SquareButton(5, on_render=collect), handle_error=False)
    button = rc.find(v.Btn, children=["Run"]).widget
    cancel_square = True
    try:
        square._start_event.clear()  # type: ignore
        button.click()
        square._start_event.set()  # type: ignore
        assert square._last_finished_event  # type: ignore
        square._last_finished_event.wait()  # type: ignore
        assert results == [
            (TaskState.NOTCALLED, None),
            (TaskState.STARTING, None),
            (TaskState.RUNNING, None),
            (TaskState.CANCELLED, None),
        ]
    finally:
        cancel_square = False
    results.clear()
    square.retry()
    square._last_finished_event.wait()  # type: ignore
    assert results == [
        (TaskState.STARTING, None),
        (TaskState.RUNNING, None),
        (TaskState.FINISHED, 5**2),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("run_in_thread", [True, False])
async def test_task_async_cancel_retry(run_in_thread):
    global cancel_square_async
    results = []

    assert square_async._instance.value.run_in_thread  # type: ignore
    square_async._instance.value.run_in_thread = run_in_thread  # type: ignore

    # ugly reset
    square_async._last_value = None

    def collect():
        results.append((square_async._result.value._state, square_async.value))

    box, rc = solara.render(SquareButtonAsync(5, on_render=collect), handle_error=False)
    button = rc.find(v.Btn, children=["Run"]).widget
    cancel_square_async = True
    try:
        square_async._start_event.clear()  # type: ignore
        button.click()
        square_async._start_event.set()  # type: ignore
        assert square_async.current_future  # type: ignore
        try:
            await square_async.current_future  # type: ignore
        except asyncio.CancelledError:
            pass

        assert results == [
            (TaskState.NOTCALLED, None),
            (TaskState.STARTING, None),
            (TaskState.RUNNING, None),
            (TaskState.CANCELLED, None),
        ]
    finally:
        cancel_square_async = False
    results.clear()
    square_async.retry()
    await square_async.current_future  # type: ignore
    assert results == [
        (TaskState.STARTING, None),
        (TaskState.RUNNING, None),
        (TaskState.FINISHED, 5**2),
    ]

    square_async._instance.value.run_in_thread = True  # type: ignore


def test_task_scopes(no_kernel_context):
    results1 = []
    results2 = []

    def collect1():
        results1.append((something._result.value._state, something.value))

    def collect2():
        results2.append((something._result.value._state, something.value))

    kernel1 = kernel.Kernel()
    kernel2 = kernel.Kernel()
    assert kernel_context.current_context[kernel_context.get_current_thread_key()] is None

    context1 = kernel_context.VirtualKernelContext(id="toestand-1", kernel=kernel1, session_id="session-1")
    context2 = kernel_context.VirtualKernelContext(id="toestand-2", kernel=kernel2, session_id="session-2")

    with context1:
        box1, rc1 = solara.render(ComputeButton(5, on_render=collect1), handle_error=False)
        button1 = rc1.find(v.Btn, children=["Run"]).widget

    with context2:
        box2, rc2 = solara.render(ComputeButton(5, on_render=collect2), handle_error=False)
        button2 = rc2.find(v.Btn, children=["Run"]).widget

    with context1:
        something._start_event.clear()  # type: ignore
        button1.click()
        something._start_event.set()  # type: ignore
        finished_event1 = something._last_finished_event  # type: ignore
        assert finished_event1

    with context2:
        assert something._last_finished_event is not finished_event1  # type: ignore
        assert something._last_finished_event is None  # type: ignore

    finished_event1.wait()
    assert results1 == [
        (TaskState.NOTCALLED, None),
        (TaskState.STARTING, None),
        (TaskState.RUNNING, None),
        (TaskState.FINISHED, "4242424242"),
    ]
    # results1.clear()
    assert results2 == [(TaskState.NOTCALLED, None)]

    with context2:
        something._start_event.clear()  # type: ignore
        button2.click()
        something._start_event.set()  # type: ignore
        finished_event2 = something._last_finished_event  # type: ignore
        assert finished_event2
    finished_event2.wait()
    assert results2 == [
        (TaskState.NOTCALLED, None),
        (TaskState.STARTING, None),
        (TaskState.RUNNING, None),
        (TaskState.FINISHED, "4242424242"),
    ]


def test_task_and_computed(no_kernel_context):
    called = 0

    @Computed
    def square_minus_one():
        nonlocal called
        called += 1
        if square.latest is None:
            return None
        return square.latest - 1

    kernel1 = kernel.Kernel()
    kernel2 = kernel.Kernel()
    assert kernel_context.current_context[kernel_context.get_current_thread_key()] is None

    context1 = kernel_context.VirtualKernelContext(id="t1", kernel=kernel1, session_id="session-1")
    context2 = kernel_context.VirtualKernelContext(id="t2", kernel=kernel2, session_id="session-2")

    with context1:
        r1 = square._result
        assert len(get_storage(square._result).listeners2["t1"]) == 0
        square(5)
        assert square._last_finished_event  # type: ignore
        square._last_finished_event.wait()  # type: ignore
        # accessing will add it to the listeners
        assert len(get_storage(square._result).listeners2["t1"]) == 0
        assert square_minus_one.value == 24
        assert called == 1
        assert len(get_storage(square._result).listeners2["t1"]) == 1
        # assert square_minus_one._auto_subscriber.value.reactive_used == {square.value}

    with context2:
        r2 = square._result
        assert len(get_storage(square._result).listeners2["t2"]) == 0
        square(6)
        assert square._last_finished_event  # type: ignore
        square._last_finished_event.wait()  # type: ignore
        assert len(get_storage(square._result).listeners2["t2"]) == 0
        assert square_minus_one.value == 35
        assert called == 2
        assert len(get_storage(square._result).listeners2["t2"]) == 1
        # square_minus_one._auto_subscriber.value.reactive_used == {square.value}

    with context1:
        assert r1 is square._result
        # assert len(square.result.listeners2["t1"]) == 1
        square._last_finished_event = None  # type: ignore
        square_minus_one._auto_subscriber.value.reactive_used == {square.value}
        assert square_minus_one.value == 24
        assert called == 2
        square(7)
        square_minus_one._auto_subscriber.value.reactive_used == {square.value}
        assert square._last_finished_event  # type: ignore
        square._last_finished_event.wait()  # type: ignore
        assert square_minus_one.value == 48
        assert called == 3

    with context2:
        assert r2 is square._result
        assert square_minus_one.value == 35
        square(8)
        assert square._last_finished_event  # type: ignore
        square._last_finished_event.wait()  # type: ignore
        assert square_minus_one.value == 63
        assert called == 4


# copied from hooks_test.py


def test_use_task_intrusive_cancel():
    task = None
    last_value = 0
    seconds = 4.0

    def retry():
        pass

    @solara.component
    def Test():
        nonlocal task
        nonlocal last_value
        retry_counter, set_retry_counter = solara.use_state(0)

        nonlocal retry

        def local_retry():
            set_retry_counter(lambda x: x + 1)

        retry = local_retry

        def work():
            nonlocal last_value
            nonlocal task
            assert task is not None
            for i in range(100):
                last_value = i
                # if not cancelled, might take 4 seconds
                time.sleep(seconds / 100)
                if not task.is_current():
                    return

            return 2**42

        task = use_task(work, dependencies=[retry_counter])
        assert task is not None
        return w.Label(value="test")

    solara.render_fixed(Test(), handle_error=False)
    assert task is not None
    # result.cancel()
    # while result._state in [TaskState.STARTING, TaskState.RUNNING]:
    #     time.sleep(0.1)
    # assert result._state == TaskState.CANCELLED
    # assert last_value != 99

    # also test retry
    while task._state != TaskState.RUNNING:
        time.sleep(0.05)
    assert last_value != 99
    seconds = 0.1
    retry()
    # wait till it stops running
    while task._state == TaskState.RUNNING:
        time.sleep(0.05)
    # wait till it exits these states
    while task._state in [TaskState.STARTING, TaskState.WAITING, TaskState.RUNNING]:
        time.sleep(0.1)
    assert task._state == TaskState.FINISHED
    assert last_value == 99


@pytest.mark.asyncio
@pytest.mark.parametrize("prefer_threaded", [True, False])
async def test_use_task_async(prefer_threaded):
    task = None
    last_value = 0
    seconds = 4.0

    def retry():
        pass

    @solara.component
    def Test():
        nonlocal task
        nonlocal last_value
        retry_counter, set_retry_counter = solara.use_state(0)
        nonlocal retry

        def local_retry():
            set_retry_counter(lambda x: x + 1)

        retry = local_retry

        async def work():
            nonlocal last_value
            assert task is not None
            for i in range(100):
                last_value = i
                # if not cancelled, might take 4 seconds
                await asyncio.sleep(seconds / 100)
                if not task.is_current():
                    return
            return 2**42

        task = use_task(work, dependencies=[retry_counter], prefer_threaded=prefer_threaded)
        return w.Label(value="test")

    solara.render_fixed(Test(), handle_error=False)
    assert task is not None
    # we do not support cancel anymore in use_task
    # result.cancel()
    # the current implementation if cancel is direct, we so we not need the code below
    # n = 0
    # while result.state in [TaskState.NOTCALLED, TaskState.STARTING, TaskState.RUNNING]:
    #     await asyncio.sleep(0.1)
    #     n += 1
    #     if n == 100:
    #         raise TimeoutError("took too long, state = " + str(result.state))
    # assert result._state == TaskState.CANCELLED
    # assert last_value != 99

    # also test retry
    seconds = 0.1
    retry()
    n = 0
    while task._state == TaskState.CANCELLED:
        await asyncio.sleep(0.1)
        n += 1
        if n == 100:
            raise TimeoutError("took too long, state = " + str(task._state))
    n = 0
    while task._state in [TaskState.STARTING, TaskState.RUNNING]:
        await asyncio.sleep(0.1)
        n += 1
        if n == 100:
            raise TimeoutError("took too long, state = " + str(task._state))
    assert task._state == TaskState.FINISHED
    assert last_value == 99


@solara.lab.task
async def task_run_async():
    print("running task_run_async")
    return 42


@solara.lab.task
def task_threaded_run_async():
    print("running task_threaded_run_async!")
    task_run_async()


def test_run_async_task_from_threaded():
    @solara.component
    def Test():
        with solara.Column():
            if task_threaded_run_async.error:
                solara.Error("Error: " + str(task_threaded_run_async.exception))
            elif task_run_async.finished:
                solara.Info("Done: " + str(task_run_async.value))
            else:
                solara.Button("Run", on_click=lambda: task_threaded_run_async())

    box, rc = solara.render(Test(), handle_error=False)
    button = rc.find(v.Btn, children=["Run"]).widget
    button.click()
    rc.find(children=["Done: 42"]).wait_for()


def test_update_while_rendering():
    some_reactive_var = solara.reactive(10)

    @solara.lab.task
    def update_task():
        print("execute update_task")
        time.sleep(0.1)
        # this update will happen before the render of Child2 is finished
        some_reactive_var.value = 20
        print("update_task done")

    @solara.component
    def Child1():
        print("rendering child1 with value", some_reactive_var.value)

    @solara.component
    def Child2():
        print("rendering child2 with value", some_reactive_var.value)
        solara.Text(f"value = {some_reactive_var.value}")
        time.sleep(0.2)

    @solara.component
    def Test():
        print("rendering parent with value", some_reactive_var.value)
        # solara.use_effect(update_task, [])
        if update_task.not_called:
            update_task()
        with solara.Column():
            Child1()
            Child2()

    box, rc = solara.render(Test(), handle_error=False)
    rc.find(children=["value = 20"]).wait_for(timeout=3)


def test_task_decorator_warning_in_component():
    with pytest.warns(UserWarning, match=r"You are calling task.*"):

        @solara.component
        def ComponentWithTask():
            @solara.tasks.task
            def my_task_in_component():
                return "done"

            return solara.Text("ComponentWithTask")

        solara.render(ComponentWithTask(), handle_error=False)

    # Test that no warning is issued when task is used with use_memo
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # Treat all warnings as errors

        @solara.component
        def ComponentWithTaskInMemo():
            def my_job_for_memo():
                return "done"

            solara.use_memo(lambda: solara.tasks.task(my_job_for_memo), dependencies=[])
            return solara.Text("ComponentWithTaskInMemo")

        solara.render_fixed(ComponentWithTaskInMemo(), handle_error=False)
