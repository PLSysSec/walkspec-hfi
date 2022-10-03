scripts:
	python ./walkspec.py

walkspec_deps:
	./get-wabt.sh

clean:
	rm -rf ./wabt-1.0.20*
