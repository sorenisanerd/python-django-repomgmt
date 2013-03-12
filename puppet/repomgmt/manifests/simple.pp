class repomgmt::simple($user = 'ubuntu',
                       $admin_name = "Admin User",
                       $admin_email = "email@example.com",
                       $dbname = "repomgmt",
                       $dbuser = "repomgmt",
                       $dbpass = "repomgmtpass",
                       $dbhost = "",
                       $dbport = "",
                       $secret_key = '!tuy9ozxr@zhr$8v3$41^3690dfnrim16yj8x5)4pi0bg%140l',
                       $ftp_ip = $::ipaddress,
                       $post_mk_sbuild_customisation = undef,
                       $use_ec2_metadata_service = false) {
  $simple = true
  $project_name = 'buildd'

  package { ["python-pip",
             "devscripts",
             "sbuild",
             "git",
             "apache2",
             "rabbitmq-server",
             "ubuntu-dev-tools",
             "reprepro",
             "haveged",
             "vsftpd",
             "python-dev"]:
    provider => "apt",
    ensure => "installed",
  }

  Package["python-dev"] -> Package<| provider == 'pip' |>

  package { ["django-celery",
             "django-tastypie",
             "django-registration",
             "python-novaclient",
             "south"]:
    provider => "pip",
    ensure => "installed",
    require => Package['python-pip']
  }

  package { "Django":
    provider => "pip",
    ensure => "1.4.3",
    require => Package['python-pip']
  }

  exec { "/usr/bin/pip install -e git+http://github.com/sorenh/python-django-repomgmt#egg=django-repomgmt":
    require => [Package['git'], Package['python-pip']]
  }

  user { "$user":
    ensure => "present",
    managehome => true,
    groups => "sbuild",
    shell => "/bin/bash",
    require => Package['sbuild']
  }

  exec { "/usr/local/bin/django-admin.py startproject buildd":
    creates => "/home/$user/buildd",
    cwd => "/home/$user",
    user => $user
  } ->
  file { "/home/$user/buildd/buildd/settings.py":
    content => template('repomgmt/settings.py.erb'),
    owner => $user
  } ->
  file { "/home/$user/buildd/buildd/urls.py":
    content => template('repomgmt/urls.py.erb'),
    owner => $user
  } ~>
  exec { "/usr/bin/python /home/$user/buildd/manage.py syncdb --noinput":
    user => $user,
    refreshonly => true
  } ~>
  exec { "/usr/bin/python /home/$user/buildd/manage.py migrate djcelery --noinput":
    user => $user,
    refreshonly => true
  } ~>
  exec { "/usr/bin/python /home/$user/buildd/manage.py migrate repomgmt --noinput":
    user => $user,
    refreshonly => true
  } ~>
  exec { "/usr/bin/python /home/$user/buildd/manage.py migrate tastypie --noinput":
    user => $user,
    refreshonly => true
  }

  file { "/etc/vsftpd.conf":
    content => template('repomgmt/vsftpd.conf.erb'),
    mode => 0644,
    owner => root,
    group => root,
    require => Package[vsftpd],
    notify => Exec["reload-vsftpd"]
  } 

  file { "/srv/ftp/incoming":
    ensure => directory,
    owner => $user,
    group => ftp,
    mode => "2711",
    require => Package[vsftpd],
  }

  exec { "reload-vsftpd":
    command => "/sbin/restart vsftpd",
    refreshonly => true
  }

  file { "/etc/apache2/conf.d/repomgmt.conf":
    content => template('repomgmt/apache.conf.erb'),
    owner => $user,
    require => Package["apache2"]
  } ~>
  exec { "/etc/init.d/apache2 reload":
    refreshonly => true
  } 
}
