CC ?= cc
CFLAGS = -std=c11 -Wall -Wextra -Werror -pedantic -O2 -Isrc
SANFLAGS = -std=c11 -Wall -Wextra -Werror -pedantic -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Isrc
SRC = src/hb_awb_stages.c src/hb_awb_recalib.c src/hb_awb_frame_stats.c src/hb_awb_scene_prepare.c
all: build/tests_opt build/tests_frame_opt build/tests_prepare_opt build/libhbstages.so
build:
	mkdir -p build
build/tests_opt: $(SRC) tests/test_stages.c | build
	$(CC) $(CFLAGS) -o $@ $^
build/tests_san: $(SRC) tests/test_stages.c | build
	$(CC) $(SANFLAGS) -o $@ $^
build/tests_frame_opt: $(SRC) tests/test_frame_stats.c | build
	$(CC) $(CFLAGS) -o $@ $^
build/tests_frame_san: $(SRC) tests/test_frame_stats.c | build
	$(CC) $(SANFLAGS) -o $@ $^
build/tests_prepare_opt: $(SRC) tests/test_scene_prepare.c | build
	$(CC) $(CFLAGS) -o $@ $^
build/tests_prepare_san: $(SRC) tests/test_scene_prepare.c | build
	$(CC) $(SANFLAGS) -o $@ $^
build/libhbstages.so: $(SRC) | build
	$(CC) $(CFLAGS) -fPIC -shared -o $@ $^
check: all build/tests_san build/tests_frame_san build/tests_prepare_san
	./build/tests_opt
	./build/tests_san
	./build/tests_frame_opt
	./build/tests_frame_san
	./build/tests_prepare_opt
	./build/tests_prepare_san
	python3 tests/test_frame_stats_python.py
	python3 tests/test_accumulation_python.py
	python3 tests/test_components_python.py
	python3 tests/test_scene_prepare_python.py
clean:
	rm -rf build
.PHONY: all check clean