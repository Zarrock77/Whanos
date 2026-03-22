folder("Whanos base images") {
	description("The base images of whanos.")
}

available_languages = ['c', 'java', 'javascript', 'python', 'befunge']

for (language in available_languages) {
    freeStyleJob("Whanos base images/whanos-${language}") {
        steps {
            shell("docker build -t whanos-${language}:latest - < /images/${language}/Dockerfile.base")
        }
    }
}

freeStyleJob("Whanos base images/Build all base images") {
	publishers {
		downstream(
			available_languages.collect { language -> "Whanos base images/whanos-${language}" }
		)
	}
}

folder("Projects") {
	description("The projects of whanos.")
}

freeStyleJob("link-project") {
    parameters {
        stringParam('GIT_REPOSITORY_URL', '', 'Git repository URL')
        stringParam('PROJECT_NAME', '', 'Name of the project to link')
    }

    steps {
        dsl {
            text("""\
                freeStyleJob("Projects/\${PROJECT_NAME}") {
                    scm {
                        git {
                            remote {
                                url('\${GIT_REPOSITORY_URL}')
                            }
                        }
                    }
                    triggers {
                        scm('* * * * *')
                    }
                    wrappers {
                        preBuildCleanup()
                    }
                    steps {
                        shell('''
                            if [ -f Dockerfile ]; then
                                echo "Custom Dockerfile detected - Using it directly"
                                docker build -t "\$PROJECT_NAME" .
                            else
                                if [ -f Makefile ]; then
                                    echo "C project detected"
                                    cp /images/c/Dockerfile.standalone Dockerfile
                                    docker build -t "\$PROJECT_NAME" .
                                elif [ -f app/pom.xml ]; then
                                    echo "Java project detected"
                                    cp /images/java/Dockerfile.standalone Dockerfile
                                    docker build -t "\$PROJECT_NAME" .
                                elif [ -f package.json ]; then
                                    echo "JavaScript project detected"
                                    cp /images/javascript/Dockerfile.standalone Dockerfile
                                    docker build -t "\$PROJECT_NAME" .
                                elif [ -f requirements.txt ]; then
                                    echo "Python project detected"
                                    cp /images/python/Dockerfile.standalone Dockerfile
                                    docker build -t "\$PROJECT_NAME" .
                                elif [ -f app/main.bf ]; then
                                    echo "Befunge project detected"
                                    cp /images/befunge/Dockerfile.standalone Dockerfile
                                    docker build -t "\$PROJECT_NAME" .
                                fi
                            fi

                            docker push "\$PROJECT_NAME"

                            if [ -f whanos.yml ]; then
                                echo "whanos.yml detected - Deploying to Kubernetes"
                                kubectl apply -f /kubernetes/deployment.yml
                                kubectl apply -f /kubernetes/service.yml
                            fi
                        ''')
                    }
                }
            """.stripIndent())
        }
    }
}
